"""
ValUprop.in — Email Service
backend/email_service.py

Sends the branded PDF report to the user after payment.
Provider: Resend (resend.com) — free tier: 3,000 emails/month

SETUP:
  pip install resend
  Add RESEND_API_KEY to .env
  Verify your domain at resend.com/domains
  Update FROM_EMAIL below with your verified domain email.

ALTERNATIVE: AWS SES (see bottom of file for swap instructions)
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("valuprop.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL     = os.getenv("FROM_EMAIL", "reports@valuprop.in")
FROM_NAME      = os.getenv("FROM_NAME", "valUProp.in")


async def send_report_email(
    to_email:     str,
    valuation_id: int,
    report_data:  dict,
    area_data:    dict,
    pdf_url:      str = None,
) -> bool:
    """
    Send the detailed valuation report to the user.
    Returns True on success, False on failure.
    """
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email delivery")
        return False

    try:
        subject  = _build_subject(area_data)
        pdf_button = f"""
        <tr>
          <td style="padding:20px 24px;text-align:center;background:#EBF3FF;border-top:1px solid #E5E7EB;">
            <a href="{pdf_url}" style="display:inline-block;background:#1B3F6E;color:white;
              padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;
              text-decoration:none;font-family:Arial,sans-serif;">
              ⬇ Download PDF Report
            </a>
            <div style="font-size:11px;color:#9CA3AF;margin-top:8px;">Link valid for 7 days</div>
          </td>
        </tr>""" if pdf_url else ""
        html     = _build_html_email(valuation_id, report_data, area_data, pdf_button=pdf_button)

        import resend
        resend.api_key = RESEND_API_KEY

        params = {
            "from":    f"{FROM_NAME} <{FROM_EMAIL}>",
            "to":      [to_email],
            "subject": subject,
            "html":    html,
        }

        email = resend.Emails.send(params)
        logger.info(f"Email sent: to={to_email} id={email.get('id')} val={valuation_id}")
        return True

    except Exception as e:
        logger.error(f"Email failed: to={to_email} val={valuation_id} error={e}")
        return False


def _build_subject(area_data: dict) -> str:
    locality = area_data.get("locality", "your property")
    city     = area_data.get("city", "")
    prop_type = {
        "Apartment": "Apartment", "IndependentHouse": "Independent House",
        "Villa": "Villa", "LandPlot": "Land/Plot"
    }.get(area_data.get("type", ""), "Property")
    return f"Your valUProp Valuation Report — {prop_type} in {locality}, {city}"


def _build_html_email(valuation_id: int, report: dict, area_data: dict, pdf_button: str = "") -> str:
    """Build the HTML email with the full report inline."""

    locality  = area_data.get("locality", "")
    city      = area_data.get("city", "")
    prop_type = area_data.get("type", "Property")

    # Format values
    vmin = report.get("value_min", 0)
    vmax = report.get("value_max", 0)
    conf = report.get("confidence_score", 70)

    def fmt(lakhs):
        if lakhs >= 100:
            return f"₹{lakhs/100:.2f} Cr"
        return f"₹{lakhs} L"

    val_range  = f"{fmt(vmin)} – {fmt(vmax)}"
    conf_color = "#1A7A4A" if conf >= 70 else "#B45309"
    conf_label = "Good" if conf >= 80 else ("Moderate" if conf >= 60 else "Low")
    sections   = report.get("sections", {})
    date_str   = datetime.now().strftime("%d %b %Y")

    # Build section rows
    def sec(letter, bg="#F9FAFB"):
        s = sections.get(letter, {})
        if not s:
            return ""
        title   = s.get("title", f"Section {letter}")
        content = s.get("content", "")

        extra = ""
        if letter == "C":
            items = [
                ("Land Rate",       s.get("land_rate_range","")),
                ("Apartment Rate",  s.get("apt_rate_range","")),
                ("Guideline Value", s.get("guideline_value","")),
            ]
            extra = "".join(
                f'<tr><td style="padding:5px 0;color:#6B7280;font-size:13px;">{k}</td>'
                f'<td style="padding:5px 0;color:#111827;font-size:13px;text-align:right;">{v}</td></tr>'
                for k, v in items if v
            )
            if extra:
                extra = f'<table width="100%" style="margin-top:8px;border-collapse:collapse;">{extra}</table>'

        if letter == "D":
            items = [
                ("Land Value",        s.get("land_value","")),
                ("Building Value",    s.get("building_value","")),
                ("Location Adjustments", s.get("adjustments","")),
            ]
            extra = "".join(
                f'<tr><td style="padding:5px 0;color:#6B7280;font-size:13px;">{k}</td>'
                f'<td style="padding:5px 0;color:#111827;font-size:13px;text-align:right;">{v}</td></tr>'
                for k, v in items if v
            )
            if extra:
                extra = f'<table width="100%" style="margin-top:8px;border-collapse:collapse;">{extra}</table>'

        if letter == "F":
            risks = s.get("risk_points", [])
            if risks:
                items_html = "".join(f'<li style="margin-bottom:6px;font-size:13px;color:#374151;">{r}</li>' for r in risks)
                extra = f'<ul style="margin:8px 0 0 16px;padding:0;">{items_html}</ul>'
            content = ""   # Don't double-print content for F

        return f"""
        <tr>
          <td style="padding:16px 24px;background:{bg};border-bottom:1px solid #E5E7EB;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:0 0 6px 0;">
                  <span style="display:inline-block;width:26px;height:26px;background:#1B3F6E;color:white;
                    border-radius:5px;text-align:center;line-height:26px;font-size:12px;font-weight:700;
                    font-family:Arial,sans-serif;margin-right:8px;">{letter}</span>
                  <span style="font-size:14px;font-weight:600;color:#111827;font-family:Arial,sans-serif;">{title}</span>
                </td>
              </tr>
              {"<tr><td><p style='margin:0;font-size:13px;color:#374151;line-height:1.6;font-family:Arial,sans-serif;'>" + content + "</p></td></tr>" if content else ""}
              {"<tr><td>" + extra + "</td></tr>" if extra else ""}
            </table>
          </td>
        </tr>"""

    comparables = report.get("comparables", [])
    comp_rows = "".join(
        f"""<tr>
          <td style="padding:10px 0;border-bottom:1px solid #F3F4F6;font-family:Arial,sans-serif;">
            <div style="font-size:13px;color:#111827;">{c.get('description','')}</div>
            <div style="font-size:12px;color:#6B7280;margin-top:2px;">{c.get('price_signal','')} · <em>{c.get('source','')}</em></div>
          </td>
        </tr>"""
        for c in comparables
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

  <!-- Header -->
  <tr>
    <td style="background:#1B3F6E;padding:24px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <div style="font-size:22px;font-weight:700;color:white;font-family:Arial,sans-serif;">
              valUProp<span style="color:#FFD580;">.in</span>
            </div>
            <div style="font-size:12px;color:rgba(255,255,255,0.65);margin-top:3px;">Independent Market Valuation</div>
          </td>
          <td align="right">
            <div style="font-size:11px;color:rgba(255,255,255,0.65);">Report Date: {date_str}</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.65);margin-top:2px;">Ref: VUP-{valuation_id:05d}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Property + Value -->
  <tr>
    <td style="padding:20px 28px;border-bottom:1px solid #E5E7EB;">
      <div style="font-size:12px;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Property</div>
      <div style="font-size:15px;color:#111827;font-weight:600;">{area_data.get('address', locality + ', ' + city)}</div>
    </td>
  </tr>

  <!-- Estimate Banner -->
  <tr>
    <td style="padding:24px 28px;background:#EBF3FF;border-bottom:1px solid #E5E7EB;">
      <div style="font-size:11px;color:#1B3F6E;text-transform:uppercase;letter-spacing:0.7px;font-weight:700;margin-bottom:8px;">ESTIMATED MARKET VALUE</div>
      <div style="font-size:32px;font-weight:700;color:#1B3F6E;">{val_range}</div>
      <div style="font-size:12px;color:#6B7280;margin-top:6px;">Excl. registration charges &amp; taxes</div>
      <div style="margin-top:10px;display:inline-block;background:{conf_color};color:white;
          padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;">
        Confidence: {conf}% — {conf_label}
      </div>
      {"<div style='margin-top:10px;font-size:12px;color:#B45309;background:#FEF3C7;padding:8px 12px;border-radius:6px;'>⚠️ Confidence below 70% — we recommend consulting a registered valuer for this property.</div>" if conf < 70 else ""}
    </td>
  </tr>

  <!-- Sections A–G -->
  <table width="100%" cellpadding="0" cellspacing="0">
    {sec("A")}
    {sec("B", "#FAFAFA")}
    {sec("C")}
    {sec("D", "#FAFAFA")}
    {sec("E")}
    {sec("F", "#FAFAFA")}
  </table>

  <!-- Comparables -->
  {"<tr><td style='padding:16px 24px;border-bottom:1px solid #E5E7EB;'><div style='font-size:13px;font-weight:600;color:#111827;margin-bottom:10px;'>Comparable Pricing References</div><table width='100%' cellpadding='0' cellspacing='0'>" + comp_rows + "</table></td></tr>" if comparables else ""}

  <!-- Disclaimer -->
  <tr>
    <td style="padding:16px 24px;background:#F9FAFB;border-top:1px solid #E5E7EB;">
      <p style="margin:0;font-size:11px;color:#9CA3AF;line-height:1.6;">
        {sections.get("G",{}).get("content","This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation.")}
      </p>
    </td>
  </tr>

  <!-- Download button (shown when pdf_url is provided) -->
  {pdf_button}

  <!-- Footer -->
  <tr>
    <td style="padding:20px 28px;background:#1B3F6E;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-size:12px;color:rgba(255,255,255,0.7);">
            © 2025 valUProp.in · support@valuprop.in
          </td>
          <td align="right" style="font-size:12px;color:rgba(255,255,255,0.7);">
            <a href="https://valuprop.in/pages/refund.html" style="color:rgba(255,255,255,0.7);">Refund Policy</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ─── AWS SES alternative ─────────────────────────────────────────
# To use AWS SES instead of Resend, replace send_report_email with:
#
# import boto3
# ses = boto3.client("ses", region_name="ap-south-1")
# ses.send_email(
#     Source=f"{FROM_NAME} <{FROM_EMAIL}>",
#     Destination={"ToAddresses": [to_email]},
#     Message={
#         "Subject": {"Data": subject},
#         "Body":    {"Html": {"Data": html}},
#     },
# )
