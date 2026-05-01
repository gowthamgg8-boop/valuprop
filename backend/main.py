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

import os, hmac, hashlib, logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from fastapi.responses import StreamingResponse, RedirectResponse
from database import SessionLocal, engine
import models, llm_service, email_service, pdf_service, s3_service

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("valuprop")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ValUprop.in API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
REPORT_PRICE_PAISE  = int(os.getenv("REPORT_PRICE_PAISE", "9900"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/property/submit")
async def submit_property(req: PropertySubmitRequest, bg: BackgroundTasks,
                          request: Request, db=Depends(get_db)):
    """Receive form → save to DB → trigger free LLM estimate (async)."""
    ip = request.client.host if request.client else "unknown"

    # Save user if lead data provided
    user = None
    if req.phone or req.email:
        user = db.query(models.User).filter(
            (models.User.phone == req.phone) | (models.User.email == req.email)
        ).first()
        if not user:
            user = models.User(phone=req.phone, email=req.email, ip=ip,
                               source=req.utm_source, utm_campaign=req.utm_campaign)
            db.add(user); db.flush()

    # Save property
    prop = models.Property(
        user_id=user.id if user else None,
        type=req.type, address=req.address, city=req.city,
        locality=req.locality, pincode=req.pincode,
        area_data=req.dict(exclude={"phone","email","utm_source","utm_campaign","utm_content"}),
    )
    db.add(prop); db.flush()

    # Create pending free valuation
    val = models.Valuation(property_id=prop.id, tier="free", status="pending")
    db.add(val); db.commit()

    bg.add_task(_run_free_estimate, prop.id, val.id, prop.area_data)
    logger.info(f"Submitted: prop={prop.id} type={req.type} locality={req.locality}")
    return {"property_id": prop.id, "valuation_id": val.id, "status": "processing"}


@app.post("/api/lead/capture")
async def capture_lead(req: LeadRequest, db=Depends(get_db)):
    """Save phone+email after free estimate is shown."""
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
    logger.info(f"Lead: prop={req.property_id} email={req.email}")
    return {"ok": True, "user_id": user.id}


@app.get("/api/valuation/free/{valuation_id}")
async def get_free_valuation(valuation_id: int, db=Depends(get_db)):
    """Poll for free estimate. Frontend polls every 2s."""
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
async def create_order(req: OrderRequest, db=Depends(get_db)):
    """Create Razorpay order. Returns order_id for frontend checkout."""
    val = db.query(models.Valuation).filter(models.Valuation.id == req.valuation_id).first()
    if not val:
        raise HTTPException(404, "Valuation not found")

    # Demo mode (no real key set)
    if not RAZORPAY_KEY_ID or "YOUR" in RAZORPAY_KEY_ID:
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
                      "receipt": f"vup_{req.valuation_id}",
                      "notes": {"valuation_id": str(req.valuation_id)}},
                timeout=10,
            )
            r.raise_for_status()
            order = r.json()
    except Exception as e:
        logger.error(f"Razorpay error: {e}")
        raise HTTPException(502, "Payment gateway error. Try again.")

    db.add(models.Payment(valuation_id=req.valuation_id, razorpay_order_id=order["id"],
                           amount=REPORT_PRICE_PAISE, status="created"))
    db.commit()
    return {"order_id": order["id"], "amount": REPORT_PRICE_PAISE, "mode": "live"}


@app.post("/api/payment/verify")
async def verify_payment(req: VerifyRequest, bg: BackgroundTasks, db=Depends(get_db)):
    """Verify Razorpay signature → trigger paid report generation."""
    payment = db.query(models.Payment).filter(
        models.Payment.razorpay_order_id == req.razorpay_order_id
    ).first()
    if not payment:
        raise HTTPException(404, "Payment not found")

    # Verify signature (skip in demo)
    if RAZORPAY_KEY_SECRET and "YOUR" not in RAZORPAY_KEY_SECRET:
        body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
        expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if expected != req.razorpay_signature:
            logger.warning(f"Signature mismatch: order={req.razorpay_order_id}")
            raise HTTPException(400, "Invalid payment signature")

    payment.razorpay_payment_id = req.razorpay_payment_id
    payment.razorpay_signature  = req.razorpay_signature
    payment.status  = "paid"
    payment.paid_at = datetime.now(timezone.utc)

    # Fetch property + user
    free_val = db.query(models.Valuation).filter(models.Valuation.id == req.valuation_id).first()
    prop     = db.query(models.Property).filter(models.Property.id == free_val.property_id).first() if free_val else None
    user     = db.query(models.User).filter(models.User.id == prop.user_id).first() if prop and prop.user_id else None

    # Create paid valuation record
    paid_val = models.Valuation(property_id=prop.id if prop else None, tier="paid", status="pending")
    db.add(paid_val); db.flush()
    payment.paid_valuation_id = paid_val.id
    db.commit()

    area_data  = prop.area_data if prop else {}
    user_email = user.email if user else ""
    bg.add_task(_run_paid_report, paid_val.id, area_data, user_email)

    logger.info(f"Payment verified: order={req.razorpay_order_id} paid_val={paid_val.id}")
    return {"verified": True, "paid_valuation_id": paid_val.id}


@app.get("/api/valuation/paid/{valuation_id}")
async def get_paid_valuation(valuation_id: int, db=Depends(get_db)):
    """Return full paid report JSON."""
    val = db.query(models.Valuation).filter(
        models.Valuation.id == valuation_id, models.Valuation.tier == "paid"
    ).first()
    if not val:
        raise HTTPException(404, "Paid valuation not found")
    if val.status == "pending":
        return {"status": "pending"}
    if val.status == "error":
        return {"status": "error", "message": "Report failed. Email support@valuprop.in"}
    return {
        "status": "ready", "valuation_id": val.id,
        "value_min": val.value_min, "value_max": val.value_max,
        "confidence": val.confidence, "report": val.insights,
        "generated_at": val.generated_at.isoformat() if val.generated_at else None,
    }




@app.get("/api/report/{valuation_id}/pdf")
async def get_report_pdf(valuation_id: int, db=Depends(get_db)):
    """
    Stream the PDF report for a paid valuation.
    If cached in S3 → redirect to pre-signed URL.
    If not yet uploaded → generate on-the-fly and stream.
    """
    val = db.query(models.Valuation).filter(
        models.Valuation.id == valuation_id,
        models.Valuation.tier == "paid",
        models.Valuation.status == "ready",
    ).first()
    if not val:
        raise HTTPException(404, "Paid report not found or not ready yet")

    # Check for cached S3 report
    rpt = db.query(models.Report).filter(models.Report.valuation_id == valuation_id).first()
    if rpt and rpt.s3_key:
        url = s3_service.get_presigned_url(rpt.s3_key)
        if url:
            return RedirectResponse(url=url, status_code=302)

    # Generate PDF on-the-fly
    prop = db.query(models.Property).filter(models.Property.id == val.property_id).first()
    area_data = prop.area_data if prop else {}
    try:
        pdf_bytes = pdf_service.generate_pdf(val.insights or {}, area_data, valuation_id)
    except Exception as e:
        logger.error(f"PDF on-the-fly failed: val={valuation_id} {e}")
        raise HTTPException(500, "PDF generation failed. Please try again or email support@valuprop.in")

    filename = f"ValUprop-Report-VUP-{valuation_id:05d}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# ═══════════════════════════════════════════════════════════════════
# BACKGROUND TASK RUNNERS
# ═══════════════════════════════════════════════════════════════════

async def _run_free_estimate(property_id: int, valuation_id: int, area_data: dict):
    db = SessionLocal()
    try:
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        result = await llm_service.generate_free_estimate(area_data)
        val.value_min = result.get("value_min")
        val.value_max = result.get("value_max")
        val.confidence = result.get("confidence_score")
        val.insights   = {"teaser": result.get("one_insight", "")}
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


async def _run_paid_report(valuation_id: int, area_data: dict, user_email: str):
    db = SessionLocal()
    try:
        val = db.query(models.Valuation).filter(models.Valuation.id == valuation_id).first()
        result = await llm_service.generate_paid_report(area_data)
        val.value_min = result.get("value_min")
        val.value_max = result.get("value_max")
        val.confidence = result.get("confidence_score")
        val.insights   = result
        val.llm_response = result
        val.status = "ready"
        val.generated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Paid report done: val={valuation_id}")

        # Generate PDF and upload to S3
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

        # Send email (with PDF URL if available)
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
