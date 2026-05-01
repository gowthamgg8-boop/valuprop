"""
valUProp.in — PDF Generation Service
backend/pdf_service.py

Generates a branded, print-quality PDF report from the valuation JSON.
Uses WeasyPrint (HTML → PDF) — no LaTeX, no wkhtmltopdf.

INSTALL:
  pip install weasyprint
  # Ubuntu/Debian: apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
  # macOS:         brew install pango
  # Windows:       see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html

ARCHITECTURE:
  1. Build HTML string from report JSON  →  2. WeasyPrint renders to PDF bytes
  3. Return bytes (caller decides: S3 upload or stream to browser)

Branded elements (per GPT Instructions v2.1):
  - valUProp.in header with logo shield
  - Light diagonal watermark "VALUPROP.IN"
  - Section letters A–G in brand blue boxes
  - Confidence badge (colour-coded)
  - Disclaimer footer on every page
"""

import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("valuprop.pdf")

BRAND_BLUE   = "#1B3F6E"
BRAND_ACCENT = "#D95F2B"
BRAND_GOLD   = "#C49A3C"
SUCCESS      = "#1A7A4A"
WARNING      = "#D97706"
DANGER       = "#B91C1C"


# ═══════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def generate_pdf(
    report_data: dict,
    area_data:   dict,
    valuation_id: int,
) -> bytes:
    """
    Generate a PDF report from the paid valuation JSON.

    Args:
        report_data:  Full LLM report JSON (sections A–G, comparables, confidence)
        area_data:    Original property form data
        valuation_id: DB valuation ID (used for reference number)

    Returns:
        PDF as bytes — ready to upload to S3 or stream to browser
    """
    html = _build_html(report_data, area_data, valuation_id)

    try:
        from weasyprint import HTML, CSS
        pdf_bytes = HTML(string=html, base_url=None).write_pdf(
            stylesheets=[CSS(string=_watermark_css())]
        )
        logger.info(f"PDF generated: val={valuation_id} size={len(pdf_bytes):,}b")
        return pdf_bytes

    except ImportError:
        logger.warning("WeasyPrint not installed — returning HTML bytes as fallback")
        return html.encode("utf-8")

    except Exception as e:
        logger.error(f"PDF generation failed val={valuation_id}: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════
# HTML TEMPLATE
# ═══════════════════════════════════════════════════════════════════

def _build_html(report: dict, area: dict, val_id: int) -> str:
    locality  = area.get("locality", "")
    city      = area.get("city", "")
    address   = area.get("address", f"{locality}, {city}")
    prop_type = _type_label(area.get("type", "Property"))
    date_str  = datetime.now().strftime("%d %b %Y")
    ref       = f"VUP-{val_id:05d}"

    vmin = report.get("value_min", 0)
    vmax = report.get("value_max", 0)
    conf = report.get("confidence_score", 70)

    val_range   = f"{_fmt(vmin)} – {_fmt(vmax)}"
    conf_color  = SUCCESS if conf >= 70 else (WARNING if conf >= 50 else DANGER)
    conf_label  = "Good" if conf >= 80 else ("Moderate" if conf >= 60 else "Low — Consult a Professional")
    sections    = report.get("sections", {})
    comparables = report.get("comparables", [])

    sec_html = ""
    for letter in ["A", "B", "C", "D", "E", "F", "G"]:
        sec_html += _render_section(letter, sections.get(letter, {}))

    comp_html = ""
    if comparables:
        rows = "".join(
            f"""<tr>
                  <td class="comp-desc">{c.get('description','')}</td>
                  <td class="comp-signal">{c.get('price_signal','')}</td>
                  <td class="comp-source">{c.get('source','')}</td>
                </tr>"""
            for c in comparables
        )
        comp_html = f"""
        <div class="section-card">
          <div class="section-head">
            <span class="sec-badge" style="background:#6B7280;">~</span>
            <span class="sec-title">Comparable Pricing References</span>
          </div>
          <table class="comp-table">
            <thead>
              <tr><th>Property</th><th>Price Signal</th><th>Source</th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    conf_warn = ""
    if conf < 70:
        conf_warn = f"""<div class="conf-warn">
          ⚠️ Confidence score is below 70%. We recommend consulting a registered valuer
          before making any financial decisions on this property.
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <style>{_main_css()}</style>
</head>
<body>

  <!-- Watermark (rendered by WeasyPrint CSS) -->
  <div class="watermark">VALUPROP.IN</div>

  <!-- HEADER -->
  <div class="page-header">
    <div class="header-brand">
      <div class="header-shield">
        <svg viewBox="0 0 20 20" fill="white" width="16" height="16">
          <path d="M10 2L3 6v5c0 4.1 3 7.9 7 8.9 4-1 7-4.8 7-8.9V6L10 2z"/>
        </svg>
      </div>
      <div>
        <div class="header-logo">valUProp<span style="color:#FFD580;">.in</span></div>
        <div class="header-subtitle">Independent Market Valuation</div>
      </div>
    </div>
    <div class="header-meta">
      <div><strong>Report Date:</strong> {date_str}</div>
      <div><strong>Reference:</strong> {ref}</div>
      <div><strong>Type:</strong> {prop_type}</div>
    </div>
  </div>

  <!-- PROPERTY + VALUE BANNER -->
  <div class="value-banner">
    <div class="banner-property">
      <div class="banner-label">PROPERTY</div>
      <div class="banner-address">{address}</div>
    </div>
    <div class="banner-value-block">
      <div class="banner-label">ESTIMATED MARKET VALUE</div>
      <div class="banner-value">{val_range}</div>
      <div class="banner-sub">Excluding registration charges &amp; taxes</div>
      <div class="conf-badge" style="background:{conf_color};">
        Confidence: {conf}% — {conf_label}
      </div>
    </div>
  </div>

  {conf_warn}

  <!-- SECTIONS A–G -->
  {sec_html}

  <!-- COMPARABLES -->
  {comp_html}

  <!-- PAGE FOOTER (repeats on every page via CSS) -->
  <div class="page-footer">
    <span>valUProp.in · AI-Powered Property Valuation · India</span>
    <span>{ref} · {date_str}</span>
    <span>Not a statutory or bank-certified valuation</span>
  </div>

</body>
</html>"""


def _render_section(letter: str, sec: dict) -> str:
    if not sec:
        return ""

    title   = sec.get("title", f"Section {letter}")
    content = sec.get("content", "")

    # Build data rows for sections C and D
    data_rows = ""
    if letter == "C":
        items = [
            ("Land Rate Range",    sec.get("land_rate_range", "")),
            ("Apartment Rate",     sec.get("apt_rate_range",  "")),
            ("Guideline Value",    sec.get("guideline_value", "")),
        ]
        rows = "".join(
            f'<tr><td class="dt-key">{k}</td><td class="dt-val">{v}</td></tr>'
            for k, v in items if v
        )
        if rows:
            data_rows = f'<table class="data-table">{rows}</table>'

    elif letter == "D":
        items = [
            ("Land Value",               sec.get("land_value",     "")),
            ("Building Value (Depr.)",   sec.get("building_value", "")),
            ("Location Adjustments",     sec.get("adjustments",    "")),
        ]
        rows = "".join(
            f'<tr><td class="dt-key">{k}</td><td class="dt-val">{v}</td></tr>'
            for k, v in items if v
        )
        if rows:
            data_rows = f'<table class="data-table">{rows}</table>'

    elif letter == "E":
        val_range = sec.get("value_range", "")
        if val_range:
            data_rows = f'<div class="opinion-range">{val_range}</div>'

    elif letter == "F":
        risks = sec.get("risk_points", [])
        if risks:
            items_html = "".join(
                f'<li class="risk-item"><span class="risk-bullet">•</span>{r.lstrip("•- ")}</li>'
                for r in risks if r.strip()
            )
            data_rows = f'<ul class="risk-list">{items_html}</ul>'
            content   = ""  # Don't duplicate F content

    # Section colour accent
    is_opinion    = letter == "E"
    is_disclaimer = letter == "G"
    card_style    = 'style="border-color:#1B3F6E;background:#EBF3FF;"' if is_opinion else \
                    'style="background:#F9FAFB;"' if is_disclaimer else ""

    return f"""
    <div class="section-card" {card_style}>
      <div class="section-head">
        <span class="sec-badge">{letter}</span>
        <span class="sec-title">{title}</span>
      </div>
      <div class="section-body">
        {data_rows}
        {"<p class='sec-content'>" + content + "</p>" if content else ""}
      </div>
    </div>"""


# ═══════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════

def _main_css() -> str:
    return f"""
    @page {{
      size: A4;
      margin: 18mm 16mm 22mm 16mm;
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #9CA3AF;
        font-family: Arial, sans-serif;
      }}
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: Arial, Helvetica, sans-serif;
      font-size: 10pt;
      color: #18202E;
      line-height: 1.55;
    }}

    /* ── Header ── */
    .page-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      background: {BRAND_BLUE};
      color: white;
      padding: 14px 18px;
      border-radius: 8px;
      margin-bottom: 14px;
    }}
    .header-brand {{ display: flex; align-items: center; gap: 12px; }}
    .header-shield {{
      width: 36px; height: 36px; border-radius: 8px;
      background: rgba(255,255,255,0.15);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }}
    .header-logo  {{ font-size: 20pt; font-weight: 700; color: white; }}
    .header-subtitle {{ font-size: 8.5pt; opacity: 0.7; margin-top: 2px; }}
    .header-meta  {{ font-size: 8.5pt; opacity: 0.8; text-align: right; line-height: 1.8; }}

    /* ── Value banner ── */
    .value-banner {{
      background: #EBF3FF;
      border: 1.5px solid {BRAND_BLUE};
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 12px;
      display: flex;
      gap: 20px;
      justify-content: space-between;
      align-items: flex-start;
    }}
    .banner-label  {{ font-size: 7.5pt; font-weight: 700; letter-spacing: 0.8px; color: {BRAND_BLUE}; margin-bottom: 5px; }}
    .banner-address{{ font-size: 11pt; font-weight: 600; color: #111827; }}
    .banner-value  {{ font-size: 22pt; font-weight: 700; color: {BRAND_BLUE}; margin-bottom: 3px; }}
    .banner-sub    {{ font-size: 8pt; color: #6B7280; margin-bottom: 8px; }}
    .banner-value-block {{ text-align: right; }}

    .conf-badge {{
      display: inline-block;
      color: white; font-size: 8.5pt; font-weight: 600;
      padding: 3px 12px; border-radius: 20px;
    }}
    .conf-warn {{
      background: #FEF3C7; border: 1px solid #F59E0B;
      border-radius: 6px; padding: 10px 14px;
      font-size: 9pt; color: #78350F;
      margin-bottom: 12px;
    }}

    /* ── Section cards ── */
    .section-card {{
      border: 1px solid #E0E4EC;
      border-radius: 8px;
      margin-bottom: 10px;
      overflow: hidden;
      page-break-inside: avoid;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      gap: 10px;
      background: #F6F7FA;
      padding: 9px 14px;
      border-bottom: 1px solid #E0E4EC;
    }}
    .sec-badge {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 24px; height: 24px; border-radius: 6px;
      background: {BRAND_BLUE}; color: white;
      font-size: 10pt; font-weight: 700; flex-shrink: 0;
    }}
    .sec-title {{ font-size: 10.5pt; font-weight: 700; color: #111827; }}

    .section-body {{ padding: 12px 14px; }}
    .sec-content  {{ font-size: 9.5pt; color: #374151; line-height: 1.65; margin-top: 8px; }}

    /* ── Data tables (C, D) ── */
    .data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
    .dt-key {{ font-size: 9pt; color: #6B7280; padding: 5px 0; border-bottom: 1px solid #F3F4F6; width: 55%; }}
    .dt-val {{ font-size: 9pt; color: #111827; font-weight: 600; padding: 5px 0; border-bottom: 1px solid #F3F4F6; text-align: right; }}

    /* ── Section E — value opinion ── */
    .opinion-range {{
      font-size: 18pt; font-weight: 700; color: {BRAND_BLUE};
      margin-bottom: 8px;
    }}

    /* ── Section F — risk list ── */
    .risk-list {{ list-style: none; padding: 0; margin: 0; }}
    .risk-item {{ display: flex; gap: 8px; align-items: flex-start; padding: 5px 0; border-bottom: 1px solid #F3F4F6; font-size: 9.5pt; color: #374151; }}
    .risk-item:last-child {{ border-bottom: none; }}
    .risk-bullet {{ color: {BRAND_ACCENT}; font-size: 12pt; line-height: 1.2; flex-shrink: 0; }}

    /* ── Comparables table ── */
    .comp-table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
    .comp-table th {{ text-align: left; padding: 6px 8px; background: #F6F7FA; color: #6B7280; font-size: 8.5pt; border-bottom: 1.5px solid #E0E4EC; }}
    .comp-desc   {{ padding: 8px 8px; color: #111827; font-weight: 500; border-bottom: 1px solid #F3F4F6; }}
    .comp-signal {{ padding: 8px 8px; color: {BRAND_BLUE}; font-weight: 600; border-bottom: 1px solid #F3F4F6; white-space: nowrap; }}
    .comp-source {{ padding: 8px 8px; color: #9CA3AF; font-size: 8.5pt; border-bottom: 1px solid #F3F4F6; }}

    /* ── Footer ── */
    .page-footer {{
      position: fixed; bottom: -14mm; left: 0; right: 0;
      display: flex; justify-content: space-between;
      font-size: 7.5pt; color: #9CA3AF;
      padding: 6px 16mm;
      border-top: 1px solid #E0E4EC;
    }}
    """


def _watermark_css() -> str:
    """Diagonal watermark rendered on every page via CSS."""
    return """
    @page {
      background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Ctext transform='translate(200,200) rotate(-35)' text-anchor='middle' font-family='Arial' font-size='28' fill='%231B3F6E' fill-opacity='0.04' font-weight='700'%3EVALUPROP.IN%3C/text%3E%3C/svg%3E");
    }
    .watermark { display: none; }
    """


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _fmt(lakhs: float) -> str:
    if not lakhs:
        return "—"
    if lakhs >= 100:
        return f"₹{lakhs/100:.2f} Cr"
    return f"₹{lakhs:.1f} L"


def _type_label(t: str) -> str:
    return {
        "Apartment":       "Apartment / Flat",
        "IndependentHouse":"Independent House",
        "Villa":           "Villa",
        "LandPlot":        "Land / Plot",
    }.get(t, t)
