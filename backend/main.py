"""
ValUprop.in — FastAPI Backend (Phase 2)
backend/main.py

Full backend: LLM valuation, PostgreSQL, Razorpay, email delivery.

QUICK START:
  cd backend
  python -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env    ← fill in your keys
  python init_db.py       ← creates tables
  uvicorn main:app --reload --port 8000
"""

import os, hmac, hashlib, logging, secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request as _StarletteRequest
from pydantic import BaseModel
from dotenv import load_dotenv

from fastapi.responses import StreamingResponse, RedirectResponse
from database import SessionLocal, engine
import models, llm_service, email_service, pdf_service, s3_service, valuation_engine
from locality_db import RATE_DATA_VERSION

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("valuprop")


# ═══════════════════════════════════════════════════════════════════
# OWASP A02 — PII masking for logs
# ═══════════════════════════════════════════════════════════════════

def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "<none>"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" if local else "*"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def mask_phone(phone: str) -> str:
    if not phone:
        return "<none>"
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) <= 4:
        return "****"
    return phone[: len(phone) - len(digits[-4:]) - 4] + "*****" + digits[-4:]


models.Base.metadata.create_all(bind=engine)


# ═══════════════════════════════════════════════════════════════════
# OWASP A09 — Security audit logging
# ═══════════════════════════════════════════════════════════════════

_audit_counters: dict = {}
_AUDIT_ALERT_THRESHOLDS = {
    "signature_failure": 5,
    "access_denied":     20,
}

def log_audit_event(event_type: str, severity: str = "info",
                     ip: str = None, detail: dict = None) -> None:
    detail = detail or {}
    prefix = "AUDIT-CRITICAL" if severity == "critical" else "AUDIT"
    logger.info(f"{prefix} event={event_type} severity={severity} ip={ip or '-'} detail={detail}")
    try:
        db = SessionLocal()
        try:
            db.add(models.AuditEvent(
                event_type=event_type, severity=severity,
                ip=ip, detail=detail,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Audit DB write failed (event={event_type}): {e}")
    threshold = _AUDIT_ALERT_THRESHOLDS.get(event_type)
    if threshold:
        _audit_counters[event_type] = _audit_counters.get(event_type, 0) + 1
        count = _audit_counters[event_type]
        if count == threshold:
            logger.info(
                f"AUDIT-CRITICAL event=threshold_breach type={event_type} "
                f"count={count} — possible attack in progress"
            )
            _send_security_alert_email(event_type, count, ip, detail)


def _send_security_alert_email(event_type: str, count: int,
                                ip: str = None, detail: dict = None) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        logger.warning("Security alert not emailed — RESEND_API_KEY not set")
        return
    try:
        import resend
        resend.api_key = api_key
        from_email = os.getenv("FROM_EMAIL", "reports@valuprop.in")
        from_name  = os.getenv("FROM_NAME", "valUProp.in")
        body = (
            f"<h2>valUProp security alert</h2>"
            f"<p>A security threshold has been breached on the API.</p>"
            f"<ul>"
            f"<li><b>Event type:</b> {event_type}</li>"
            f"<li><b>Count since startup:</b> {count}</li>"
            f"<li><b>Last source IP:</b> {ip or 'unknown'}</li>"
            f"<li><b>Detail:</b> {detail or {}}</li>"
            f"</ul>"
            f"<p>Check the audit_events table and Render logs "
            f"(search 'AUDIT-CRITICAL') for the full picture.</p>"
        )
        resend.Emails.send({
            "from":    f"{from_name} <{from_email}>",
            "to":      [SECURITY_ALERT_EMAIL],
            "subject": f"[valUProp SECURITY] {event_type} threshold breached",
            "html":    body,
        })
        logger.info(f"Security alert emailed to {SECURITY_ALERT_EMAIL} (event={event_type})")
    except Exception as e:
        logger.error(f"Security alert email failed (event={event_type}): {e}")


_DEFAULT_ALLOWED_ORIGINS = (
    "https://valuprop-frontend.onrender.com,"
    "https://valuprop.in,"
    "https://www.valuprop.in"
)
ALLOWED_ORIGINS = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS).split(",")
    if o.strip() and o.strip() != "*"
]

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

_docs_kwargs = (
    {"docs_url": None, "redoc_url": None, "openapi_url": None}
    if IS_PRODUCTION else {}
)

app = FastAPI(title="ValUprop.in API", version="2.0.0", **_docs_kwargs)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

def _client_ip(request: "_StarletteRequest") -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_client_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_headers(request: _StarletteRequest, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: _StarletteRequest, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again or contact info@myriky.com"},
    )

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
REPORT_PRICE_PAISE  = int(os.getenv("REPORT_PRICE_PAISE", "9900"))

SECURITY_ALERT_EMAIL = os.getenv("SECURITY_ALERT_EMAIL", "info@myriky.com")

DEMO_MODE = (
    os.getenv("DEMO_MODE", "").lower() == "yes"
    and not IS_PRODUCTION
)
if IS_PRODUCTION and not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET):
    logger.warning(
        "PRODUCTION mode but Razorpay keys missing — payment endpoints "
        "will fail. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def _verify_paid_access(valuation: "models.Valuation",
                        provided_token: Optional[str],
                        ip: str = None) -> None:
    if not provided_token:
        log_audit_event("access_denied", "warning", ip,
                         {"reason": "no_token", "valuation_id": valuation.id})
        raise HTTPException(401, "Access token required")
    if not valuation.access_token:
        log_audit_event("access_denied", "warning", ip,
                         {"reason": "no_token_issued", "valuation_id": valuation.id})
        raise HTTPException(403, "Access denied")
    if not hmac.compare_digest(provided_token, valuation.access_token):
        log_audit_event("access_denied", "warning", ip,
                         {"reason": "token_mismatch", "valuation_id": valuation.id})
        raise HTTPException(403, "Access denied")


class PropertySubmitRequest(BaseModel):
    type: str; address: str; city: str; locality: str; pincode: str
    propName: Optional[str] = ""
    bhk: Optional[str] = ""; carpetArea: Optional[str] = ""
    builtupArea: Optional[str] = ""; superBuiltup: Optional[str] = ""
    floorInfo: Optional[str] = ""; ageApt: Optional[str] = ""
    furnishing: Optional[str] = ""; parkingApt: Optional[str] = ""
    facing: Optional[str] = ""
    plotHouse: Optional[str] = ""; builtupHouse: Optional[str] = ""
    floorsHouse: Optional[str] = ""; bedroomsHouse: Optional[str] = ""
    ageHouse: Optional[str] = ""; roadHouse: Optional[str] = ""
    communityHouse: Optional[str] = ""; parkingHouse: Optional[str] = ""
    plotVilla: Optional[str] = ""; builtupVilla: Optional[str] = ""
    configVilla: Optional[str] = ""; ageVilla: Optional[str] = ""
    communityVilla: Optional[str] = ""; amenitiesVilla: Optional[str] = ""
    plotLand: Optional[str] = ""; landUse: Optional[str] = ""
    approval: Optional[str] = ""; roadLand: Optional[str] = ""
    cornerPlot: Optional[str] = ""
    phone: Optional[str] = ""; email: Optional[str] = ""
    utm_source: Optional[str] = ""; utm_campaign: Optional[str] = ""
    utm_content: Optional[str] = ""

class LeadRequest(BaseModel):
    property_id: int; phone: str; email: str

class OrderRequest(BaseModel):
    property_id: int; valuation_id: int

class VerifyRequest(BaseModel):
    razorpay_order_id: str; razorpay_payment_id: str
    razorpay_signature: str; valuation_id: int


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "rate_data_version": RATE_DATA_VERSION}


@app.post("/api/property/submit")
@limiter.limit("10/minute")
async def submit_property(req: PropertySubmitRequest, bg: BackgroundTasks,
                          request: Request, db=Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    user = None
    if req.phone or req.email:
        user = db.query(models.User).filter(
            (models.User.phone == req.phone) | (models.User.email == req.email)
        ).first()
        if not user:
            user = models.User(phone=req.phone, email=req.email, ip=ip,
                               source=req.utm_source, utm_campaign=req.utm_campaign)
            db.add(user); db.flush()
    prop = models.Property(
        user_id=user.id if user else None,
        type=req.type, address=req.address, city=req.city,
        locality=req.locality, pincode=req.pincode,
        area_data=req.dict(exclude={"phone","email","utm_source","utm_campaign","utm_content"}),
    )
    db.add(prop); db.flush()
    val = models.Valuation(property_id=prop.id, tier="free", status="pending")
    db.add(val); db.commit()
    bg.add_task(_run_free_estimate, prop.id, val.id, prop.area_data)
    logger.info(f"Submitted: prop={prop.id} type={req.type} locality={req.locality}")
    return {"property_id": prop.id, "valuation_id": val.id, "status": "processing"}


@app.post("/api/lead/capture")
@limiter.limit("20/minute")
async def capture_lead(req: LeadRequest, request: Request, db=Depends(get_db)):
    prop = db.query(models.Property).filter(models.Property.id == req.property_id).first()
    if not prop:
        raise HTTPException(404, "Property not found")
    user = db.query(models.User).filter(
        (models.User.phone == req.phone) | (models.User.email == req.email)
    ).first()
    if not user:
        user = models.User(phone=req.phone, email=req.email)
        db.add(user); db.flush()
    if not prop.user_id:
        prop.user_id = user.id
    db.commit()
    logger.info(f"Lead: prop={req.property_id} email={mask_email(req.email)}")
    return {"ok": True, "user_id": user.id}


@app.get("/api/valuation/free/{valuation_id}")
@limiter.limit("100/minute")
async def get_free_valuation(valuation_id: int, request: Request, db=Depends(get_db)):
    val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
    if not val:
        raise HTTPException(404, "Valuation not found")
    if val.status == "pending":
        return {"status": "pending"}
    if val.status == "error":
        return {"status": "error", "message": "Generation failed. Please try again."}
    return {
        "status": "ready", "valuation_id": val.id,
        "value_min": val.value_min, "value_max": val.value_max,
        "confidence": val.confidence,
        "insight": val.insights.get("teaser","") if val.insights else "",
    }


@app.post("/api/payment/create-order")
@limiter.limit("10/minute")
async def create_order(req: OrderRequest, request: Request, db=Depends(get_db)):
    val = db.query(models.Valuation).filter(models.Valuation.id == req.valuation_id).first()
    if not val:
        raise HTTPException(404, "Valuation not found")
    if DEMO_MODE:
        oid = f"demo_order_{int(datetime.now().timestamp())}"
        db.add(models.Payment(valuation_id=req.valuation_id, razorpay_order_id=oid,
                               amount=REPORT_PRICE_PAISE, status="created"))
        db.commit()
        return {"order_id": oid, "amount": REPORT_PRICE_PAISE, "mode": "demo"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                json={"amount": REPORT_PRICE_PAISE, "currency": "INR",
                      "receipt": f"valuprop_{req.valuation_id}"},
                timeout=10.0,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.error(f"Razorpay order create failed: {e}")
        raise HTTPException(500, "Payment gateway error. Please retry.")
    db.add(models.Payment(valuation_id=req.valuation_id, razorpay_order_id=data["id"],
                           amount=REPORT_PRICE_PAISE, status="created"))
    db.commit()
    return {"order_id": data["id"], "amount": REPORT_PRICE_PAISE, "mode": "live",
            "key_id": RAZORPAY_KEY_ID}


@app.post("/api/payment/verify")
@limiter.limit("5/minute")
async def verify_payment(req: VerifyRequest, request: Request, bg: BackgroundTasks, db=Depends(get_db)):
    payment = db.query(models.Payment).filter(
        models.Payment.razorpay_order_id == req.razorpay_order_id
    ).first()
    if not payment:
        raise HTTPException(404, "Order not found")
    if DEMO_MODE and req.razorpay_order_id.startswith("demo_order_"):
        logger.info(f"Demo payment accepted: {req.razorpay_order_id}")
    else:
        body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode()
        expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, req.razorpay_signature):
            log_audit_event("signature_failure", "critical", _client_ip(request),
                             {"context": "payment_verify", "order_id": req.razorpay_order_id})
            raise HTTPException(400, "Invalid payment signature")
    payment.razorpay_payment_id = req.razorpay_payment_id
    payment.razorpay_signature  = req.razorpay_signature
    payment.status  = "paid"
    payment.paid_at = datetime.now(timezone.utc)
    free_val = db.query(models.Valuation).filter(models.Valuation.id == req.valuation_id).first()
    prop     = db.query(models.Property).filter(models.Property.id == free_val.property_id).first() if free_val else None
    user     = db.query(models.User).filter(models.User.id == prop.user_id).first() if prop and prop.user_id else None
    access_token = _generate_access_token()
    paid_val = models.Valuation(
        property_id=prop.id if prop else None,
        tier="paid",
        status="pending",
        access_token=access_token,
    )
    db.add(paid_val); db.flush()
    payment.paid_valuation_id = paid_val.id
    db.commit()
    area_data  = prop.area_data if prop else {}
    user_email = user.email if user else ""
    free_range = None
    if free_val and free_val.value_min is not None and free_val.value_max is not None:
        free_range = (float(free_val.value_min), float(free_val.value_max))
    bg.add_task(_run_paid_report, paid_val.id, area_data, user_email, free_range)
    logger.info(f"Payment verified: order={req.razorpay_order_id} paid_val={paid_val.id}")
    log_audit_event("payment_verified", "info", _client_ip(request),
                     {"order_id": req.razorpay_order_id, "paid_valuation_id": paid_val.id})
    return {
        "verified": True,
        "paid_valuation_id": paid_val.id,
        "access_token": access_token,
    }


@app.post("/api/payment/webhook")
@limiter.limit("60/minute")
async def razorpay_webhook(request: Request, db=Depends(get_db)):
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.warning("Webhook call received but RAZORPAY_WEBHOOK_SECRET not set — rejected")
        raise HTTPException(503, "Webhook not configured")
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        logger.warning("Webhook signature mismatch — rejected")
        log_audit_event("signature_failure", "critical", _client_ip(request),
                         {"context": "webhook"})
        raise HTTPException(400, "Invalid webhook signature")
    import json
    try:
        event = json.loads(raw_body)
        event_type = event.get("event", "unknown")
    except Exception:
        event_type = "unparseable"
    logger.info(f"Razorpay webhook received and verified: event={event_type}")
    log_audit_event("webhook_received", "info", _client_ip(request),
                     {"event": event_type})
    return {"received": True}


@app.get("/api/valuation/paid/{valuation_id}")
@limiter.limit("100/minute")
async def get_paid_valuation(
    valuation_id: int,
    request: Request,
    token: Optional[str] = None,
    x_access_token: Optional[str] = Header(default=None),
    db=Depends(get_db),
):
    val = db.query(models.Valuation).filter(
        models.Valuation.id == valuation_id, models.Valuation.tier == "paid"
    ).first()
    if not val:
        raise HTTPException(404, "Paid valuation not found")
    _verify_paid_access(val, token or x_access_token, ip=_client_ip(request))
    if val.status == "pending":
        return {"status": "pending"}
    if val.status == "error":
        return {"status": "error", "message": "Report failed. Email info@myriky.com"}
    return {
        "status": "ready", "valuation_id": val.id,
        "value_min": val.value_min, "value_max": val.value_max,
        "confidence": val.confidence, "report": val.insights,
        "generated_at": val.generated_at.isoformat() if val.generated_at else None,
    }


@app.get("/api/report/{valuation_id}/pdf")
@limiter.limit("10/minute")
async def get_report_pdf(
    valuation_id: int,
    request: Request,
    token: Optional[str] = None,
    x_access_token: Optional[str] = Header(default=None),
    db=Depends(get_db),
):
    val = db.query(models.Valuation).filter(
        models.Valuation.id == valuation_id,
        models.Valuation.tier == "paid",
        models.Valuation.status == "ready",
    ).first()
    if not val:
        raise HTTPException(404, "Paid report not found or not ready yet")
    _verify_paid_access(val, token or x_access_token, ip=_client_ip(request))
    rpt = db.query(models.Report).filter(models.Report.valuation_id == valuation_id).first()
    if rpt and rpt.s3_key:
        url = s3_service.get_presigned_url(rpt.s3_key)
        if url:
            return RedirectResponse(url=url, status_code=302)
    prop = db.query(models.Property).filter(models.Property.id == val.property_id).first()
    area_data = prop.area_data if prop else {}
    try:
        pdf_bytes = pdf_service.generate_pdf(val.insights or {}, area_data, valuation_id)
    except Exception as e:
        logger.error(f"PDF on-the-fly failed: val={valuation_id} {e}")
        raise HTTPException(500, "PDF generation failed. Please try again or email info@myriky.com")
    filename = f"ValUprop-Report-VUP-{valuation_id:05d}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _to_property_input(area_data: dict):
    from valuation_engine import PropertyInput
    def _to_int(v):
        if v is None or v == "":
            return None
        try:
            s = str(v).strip().replace(",", "")
            num = ""
            for c in s:
                if c.isdigit() or (c == "-" and not num):
                    num += c
                else:
                    break
            return int(num) if num else None
        except (ValueError, TypeError):
            return None
    prop_type = area_data.get("type") or "Apartment"
    return PropertyInput(
        prop_type    = prop_type,
        city         = area_data.get("city") or "",
        locality     = area_data.get("locality") or "",
        address      = area_data.get("address") or "",
        pincode      = area_data.get("pincode") or "",
        prop_name    = area_data.get("propName") or "",
        bhk          = area_data.get("bhk") or "",
        carpet_area  = _to_int(area_data.get("carpetArea")),
        builtup_area = _to_int(area_data.get("builtupArea")),
        super_builtup= _to_int(area_data.get("superBuiltup")),
        floor_info   = area_data.get("floorInfo") or "",
        age_apt      = area_data.get("ageApt") or "",
        furnishing   = area_data.get("furnishing") or "",
        parking_apt  = area_data.get("parkingApt") or "",
        facing       = area_data.get("facing") or "",
        plot_house     = _to_int(area_data.get("plotHouse")),
        builtup_house  = _to_int(area_data.get("builtupHouse")),
        floors_house   = area_data.get("floorsHouse") or "",
        bedrooms_house = area_data.get("bedroomsHouse") or "",
        age_house      = _to_int(area_data.get("ageHouse")),
        road_house     = area_data.get("roadHouse") or "",
        community_house= area_data.get("communityHouse") or "",
        parking_house  = area_data.get("parkingHouse") or "",
        plot_villa     = _to_int(area_data.get("plotVilla")),
        builtup_villa  = _to_int(area_data.get("builtupVilla")),
        config_villa   = area_data.get("configVilla") or "",
        age_villa      = area_data.get("ageVilla") or "",
        community_villa= area_data.get("communityVilla") or "",
        amenities_villa= area_data.get("amenitiesVilla") or "",
        plot_land    = _to_int(area_data.get("plotLand")),
        land_use     = area_data.get("landUse") or "",
        approval     = area_data.get("approval") or "",
        road_land    = area_data.get("roadLand") or "",
        corner_plot  = area_data.get("cornerPlot") or "",
    )


async def _run_free_estimate(property_id: int, valuation_id: int, area_data: dict):
    db = SessionLocal()
    try:
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        prop_input = _to_property_input(area_data)
        free_est = await valuation_engine.generate_free_estimate(prop_input)
        from dataclasses import asdict
        result = asdict(free_est)
        val.value_min = result.get("value_lo")
        val.value_max = result.get("value_hi")
        val.confidence = result.get("confidence")
        val.insights   = {"teaser": result.get("teaser_insight", "")}
        val.llm_response = result
        val.status = "ready"
        val.generated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Free estimate done: val={valuation_id} {val.value_min}–{val.value_max} L")
    except Exception as e:
        logger.error(f"Free estimate error val={valuation_id}: {e}")
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        if val: val.status = "error"; db.commit()
    finally:
        db.close()


async def _run_paid_report(valuation_id: int, area_data: dict, user_email: str,
                           free_range: Optional[tuple] = None):
    db = SessionLocal()
    try:
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        prop_input = _to_property_input(area_data)
        paid_report = await valuation_engine.generate_detailed_report(
            prop_input, free_range=free_range
        )
        from dataclasses import asdict
        result = asdict(paid_report)
        val.value_min = result.get("value_lo")
        val.value_max = result.get("value_hi")
        val.confidence = result.get("confidence")
        val.insights   = result
        val.llm_response = result
        val.status = "ready"
        val.generated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Paid report done: val={valuation_id}")
        try:
            pdf_bytes = pdf_service.generate_pdf(result, area_data, valuation_id)
            s3_key    = s3_service.upload_pdf(pdf_bytes, valuation_id)
            if s3_key:
                report_rec = models.Report(
                    valuation_id=valuation_id, s3_key=s3_key,
                    emailed_at=None, sent_to_email=user_email,
                )
                db.add(report_rec); db.commit()
                pdf_url = s3_service.get_presigned_url(s3_key)
            else:
                pdf_url = None
        except Exception as pdf_err:
            logger.warning(f"PDF/S3 step failed (non-blocking): {pdf_err}")
            pdf_url = None
        if user_email:
            await email_service.send_report_email(
                user_email, valuation_id, result, area_data, pdf_url=pdf_url
            )
    except Exception as e:
        logger.error(f"Paid report error val={valuation_id}: {e}")
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        if val: val.status = "error"; db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
