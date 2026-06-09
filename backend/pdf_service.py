"""
valUProp.in — PDF Generation Service
backend/pdf_service.py
Generates a branded PDF report using ReportLab (pure Python, no system deps).
Falls back to WeasyPrint if available.
INSTALL:
  pip install reportlab
"""
import io
import logging
import re
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
# NORMALISE — map DetailedReport dict → pdf_service expected shape
# ═══════════════════════════════════════════════════════════════════
def _normalise(report_data: dict) -> dict:
    """
    DetailedReport (from valuation_engine.asdict) uses flat field names.
    pdf_service expects sections={A:{title,content}, ...}, value_min, value_max etc.
    This function translates between the two shapes.
    """
    # If already in the expected shape, return as-is
    if "sections" in report_data:
        return report_data

    def _risk_points(text: str) -> list:
        """Split bullet-point string into list.
        Handles newline-separated bullets AND run-on strings with embedded • markers."""
        if not text:
            return []
        # First try newline split
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        # If only 1 line but it contains multiple bullet markers, re-split on •
        if len(lines) <= 1:
            import re as _re
            parts = _re.split(r'(?<!\A)(?=•)', text)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                lines = parts
        return lines

    sections = {
        "A": {"title": "Asset Overview",            "content": report_data.get("asset_overview", "")},
        "B": {"title": "Micro-Market Context",      "content": report_data.get("micro_market", "")},
        "C": {
            "title":           "Observed Pricing Signals",
            "content":         report_data.get("pricing_signals", ""),
            "land_rate_range": (
                f"Rs.{int(report_data['land_rate_sqft_lo']):,}–Rs.{int(report_data['land_rate_sqft_hi']):,}/sqft"
                if report_data.get("land_rate_sqft_lo") else
                _fmt_range(report_data.get("land_value_lo"), report_data.get("land_value_hi"), suffix="L")
            ),
            "apt_rate_range":  (
                f"Rs.{int(report_data['apt_rate_lo']):,}–Rs.{int(report_data['apt_rate_hi']):,}/sqft"
                if report_data.get("apt_rate_lo") else ""
            ),
            "guideline_value": (
                f"Rs.{int(report_data['guideline_rate']):,}/sqft (regulatory floor)"
                if report_data.get("guideline_rate") else ""
            ),
            "trend":           report_data.get("locality_trend", ""),
        },
        "D": {
            "title":           "Valuation Build-Up",
            "content":         report_data.get("valuation_buildup", ""),
            "land_value":      _fmt_range(report_data.get("land_value_lo"), report_data.get("land_value_hi"), suffix="L"),
            "building_value":  _fmt_range(report_data.get("building_value_lo"), report_data.get("building_value_hi"), suffix="L"),
            "adjustments":     _fmt_range(report_data.get("adj_value_lo"), report_data.get("adj_value_hi"), suffix="L"),
        },
        "E": {
            "title":       "Independent Value Opinion",
            "content":     report_data.get("value_opinion", ""),
            "value_range": _fmt_range(report_data.get("value_lo"), report_data.get("value_hi"), prefix="Rs.", suffix="L"),
        },
        "F": {
            "title":        "Risk & Due Diligence",
            "content":      "",
            "risk_points":  _risk_points(report_data.get("risk_diligence", "")),
        },
        "G": {"title": "Important Disclaimer", "content": report_data.get("disclaimer", "")},
    }
    return {
        "sections":        sections,
        "value_min":       report_data.get("value_lo", 0),
        "value_max":       report_data.get("value_hi", 0),
        "confidence_score": report_data.get("confidence", 70),
        "comparables":     [],   # comparables section removed
    }

def _fmt_range(lo, hi, prefix="Rs.", suffix="L") -> str:
    if lo is None or hi is None:
        return ""
    return f"{prefix}{lo}{suffix} - {prefix}{hi}{suffix}"

def _tc(s, n: int = 300) -> str:
    """Truncate table-cell text to prevent ReportLab from creating cells taller
    than one page (which causes a fatal PDF generation error)."""
    s = str(s) if s is not None else ""
    return s[:n] + "…" if len(s) > n else s

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
    Uses ReportLab (primary) with WeasyPrint as fallback.
    """
    report_data = _normalise(report_data)
    try:
        pdf_bytes = _generate_reportlab(report_data, area_data, valuation_id)
        logger.info(f"PDF generated via ReportLab: val={valuation_id} size={len(pdf_bytes):,}b")
        return pdf_bytes
    except Exception as e:
        logger.warning(f"ReportLab failed val={valuation_id}: {e} — trying WeasyPrint")
    try:
        from weasyprint import HTML, CSS
        html = _build_html(report_data, area_data, valuation_id)
        pdf_bytes = HTML(string=html, base_url=None).write_pdf(
            stylesheets=[CSS(string=_watermark_css())]
        )
        logger.info(f"PDF generated via WeasyPrint: val={valuation_id} size={len(pdf_bytes):,}b")
        return pdf_bytes
    except Exception as e:
        logger.error(f"WeasyPrint also failed val={valuation_id}: {e}")
    raise RuntimeError("PDF generation failed — both ReportLab and WeasyPrint unavailable")

# ═══════════════════════════════════════════════════════════════════
# REPORTLAB GENERATOR
# ═══════════════════════════════════════════════════════════════════
def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))

def _generate_reportlab(report: dict, area: dict, val_id: int) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, HRFlowable, KeepTogether)
    from reportlab.lib import colors

    C_BLUE   = colors.HexColor(BRAND_BLUE)
    C_ACCENT = colors.HexColor(BRAND_ACCENT)
    C_LIGHT  = colors.HexColor("#EBF3FF")
    C_MUTED  = colors.HexColor("#6B7280")
    C_BORDER = colors.HexColor("#E0E4EC")
    C_BG     = colors.HexColor("#F6F7FA")
    C_TEXT   = colors.HexColor("#111827")

    conf     = report.get("confidence_score", 70)
    C_CONF   = colors.HexColor(SUCCESS if conf >= 70 else (WARNING if conf >= 50 else DANGER))

    locality  = area.get("locality", "")
    city      = area.get("city", "")
    address   = area.get("address", f"{locality}, {city}") or f"{locality}, {city}"
    prop_type = _type_label(area.get("type", "Property"))
    date_str  = datetime.now().strftime("%d %b %Y")
    ref       = f"VUP-{val_id:05d}"
    vmin      = report.get("value_min", 0) or 0
    vmax      = report.get("value_max", 0) or 0
    val_range = f"{_fmt(vmin)} – {_fmt(vmax)}"
    conf_label = "High" if conf >= 80 else ("Moderate" if conf >= 60 else "Low")
    sections  = report.get("sections", {})

    buf = io.BytesIO()
    PAGE_W, PAGE_H = A4
    LM = RM = 16*mm
    W = PAGE_W - LM - RM
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=18*mm, bottomMargin=22*mm)

    SS = getSampleStyleSheet()
    def S(name, **kw):
        s = ParagraphStyle(name, parent=SS["Normal"])
        for k, v in kw.items(): setattr(s, k, v)
        return s

    sN    = S("N",    fontSize=9,  leading=14, textColor=C_TEXT)
    sMu   = S("Mu",   fontSize=8,  leading=12, textColor=C_MUTED)
    sBo   = S("Bo",   fontSize=9,  leading=14, textColor=C_TEXT,  fontName="Helvetica-Bold")
    sH1   = S("H1",   fontSize=16, leading=22, textColor=C_BLUE,  fontName="Helvetica-Bold")
    sH2   = S("H2",   fontSize=11, leading=16, textColor=C_TEXT,  fontName="Helvetica-Bold")
    sWh   = S("Wh",   fontSize=9,  leading=14, textColor=colors.white)
    sWB   = S("WB",   fontSize=13, leading=18, textColor=colors.white, fontName="Helvetica-Bold")
    sWS   = S("WS",   fontSize=8,  leading=11, textColor=colors.HexColor("#CBD5E1"))
    # Content style: indented paragraph that flows freely across pages (no Table wrapper)
    sCont = S("Cont", fontSize=9,  leading=14, textColor=C_TEXT,
               leftIndent=10, rightIndent=10, spaceBefore=6, spaceAfter=6)

    story = []

    # ── HEADER ──────────────────────────────────────────────────
    h = Table([
        [Paragraph(f"<b>valUProp.in</b>  Independent Market Valuation", sWB),
         Paragraph(f"Date: {date_str} | Ref: {ref} | {prop_type}", sWS)]
    ], colWidths=[W*0.65, W*0.35], rowHeights=[36])
    h.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_BLUE),
        ("ALIGN",(1,0),(1,0),"RIGHT"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    story.append(h)
    story.append(Spacer(1, 6))

    # ── VALUE BANNER ─────────────────────────────────────────────
    b = Table([
        [Paragraph(f"<b>PROPERTY</b><br/>{address}", sBo),
         Paragraph(f"<b>ESTIMATED MARKET VALUE</b><br/>"
                   f"<font size='16'><b>{val_range}</b></font><br/>"
                   f"<font size='8'>Excl. registration charges &amp; taxes</font><br/>"
                   f"Confidence: {conf}% - {conf_label}", sBo)]
    ], colWidths=[W*0.45, W*0.55], rowHeights=[80])
    b.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),C_LIGHT),
        ("BOX",(0,0),(-1,-1),1.5,C_BLUE),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),
        ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
    ]))
    story.append(b)
    story.append(Spacer(1, 8))

    if conf < 70:
        w = Table([[Paragraph(
            "[!] Confidence below 70%. Recommend consulting a registered valuer before transacting.", sN
        )]], colWidths=[W], rowHeights=[30])
        w.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FEF3C7")),
            ("BOX",(0,0),(-1,-1),1,colors.HexColor("#F59E0B")),
            ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        story.append(w)
        story.append(Spacer(1, 6))

    # ── SECTIONS A–G ─────────────────────────────────────────────
    for letter in ["A","B","C","D","E","F","G"]:
        sec = sections.get(letter, {})
        if not sec:
            continue
        title   = sec.get("title", f"Section {letter}")
        content = sec.get("content", "")
        is_E    = letter == "E"
        bc      = C_BLUE if is_E else C_BORDER

        # Section header
        hdr = Table([[
            Paragraph(letter, S("badge", fontSize=9, leading=12,
                                textColor=colors.white, fontName="Helvetica-Bold",
                                backColor=C_BLUE, borderPadding=2)),
            Paragraph(title, sH2)
        ]], colWidths=[22, W-22], rowHeights=[28])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),C_BG if not is_E else C_LIGHT),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
            ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
            ("LINEBELOW",(0,0),(-1,-1),0.5,C_BORDER),
            ("BOX",(0,0),(-1,-1),1,bc),
        ]))

        # Collect this section's flowables; added to story at end of iteration
        sec_items = [hdr]

        # ── Section E: value range banner ──────────────────────
        if is_E:
            vr = sec.get("value_range", "")
            if vr:
                vrt = Table([[Paragraph(vr, sH1)]], colWidths=[W], rowHeights=[40])
                vrt.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,-1),C_LIGHT),
                    ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                    ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),4),
                    ("BOX",(0,0),(-1,-1),1,C_BLUE),
                ]))
                sec_items.append(vrt)

        # ── Section C: pricing signals table ───────────────────
        elif letter == "C":
            rows = []
            for k, fk in [("Land Rate Range","land_rate_range"),
                           ("Apartment Rate", "apt_rate_range"),
                           ("12-Month Trend", "trend"),
                           ("Guideline Value","guideline_value")]:
                v = sec.get(fk,"")
                if v:
                    rows.append([Paragraph(k, sMu), Paragraph(str(v), sBo)])
            if rows:
                hdr_row = [
                    Paragraph("SIGNAL", S("ch",  fontSize=7, leading=10, textColor=C_MUTED, fontName="Helvetica-Bold")),
                    Paragraph("VALUE",  S("ch2", fontSize=7, leading=10, textColor=C_MUTED, fontName="Helvetica-Bold"))
                ]
                dt = Table([hdr_row] + rows, colWidths=[W*0.55, W*0.45])
                dt.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),C_BG),
                    ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                    ("LINEBELOW",(0,0),(-1,-1),0.5,C_BORDER),
                    ("BOX",(0,0),(-1,-1),1,C_BORDER),
                ]))
                sec_items.append(dt)

        # ── Section D: Steps + Adjustments + Rental Yield ──────
        elif letter == "D":
            raw_content = sec.get("content", "")
            step_rows  = []
            adj_rows   = []
            yield_rows = []
            note_text  = ""
            final_val  = ""
            for line in raw_content.split("\n"):
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                tag = parts[0]
                if tag == "STEPS" and len(parts) >= 5:
                    step_rows.append(parts[1:5])
                elif tag == "ADJ" and len(parts) >= 4:
                    adj_rows.append(parts[1:4])
                elif tag == "FINAL" and len(parts) >= 5:
                    final_val = parts[4] if len(parts) > 4 else ""
                elif tag == "YIELD" and len(parts) >= 6:
                    yield_rows.append(parts[1:6])
                elif tag == "NOTE":
                    note_text = "|".join(parts[1:])

            # Steps table (Steps 1–4)
            if step_rows:
                shdr  = [Paragraph(h, S(f"sh{i}", fontSize=7, leading=10, textColor=C_MUTED, fontName="Helvetica-Bold"))
                         for i, h in enumerate(["STEP","COMPONENT","CALCULATION","VALUE"])]
                srows = [[Paragraph(_tc(c, 200), sBo if i==0 else (sBo if i==3 else sN)) for i,c in enumerate(r)] for r in step_rows]
                if final_val:
                    srows.append([Paragraph("", sN), Paragraph("FINAL VALUE", sBo), Paragraph("", sN),
                                  Paragraph(final_val, S("fv", fontSize=9, leading=14, textColor=C_BLUE, fontName="Helvetica-Bold"))])
                t = Table([shdr]+srows, colWidths=[W*0.12, W*0.28, W*0.33, W*0.27])
                t.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),C_BG),
                    ("BACKGROUND",(0,-1),(-1,-1),C_LIGHT),
                    ("LINEBELOW",(0,0),(-1,-1),0.5,C_BORDER),
                    ("BOX",(0,0),(-1,-1),1,C_BORDER),
                    ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ]))
                sec_items.append(t)
                sec_items.append(Spacer(1, 4))

            # Adjustments table (Step 5)
            if adj_rows:
                ahdr  = [Paragraph(h, S(f"ah{i}", fontSize=7, leading=10, textColor=C_MUTED, fontName="Helvetica-Bold"))
                         for i, h in enumerate(["STEP 5 ADJUSTMENTS","FACTOR","APPLIED"])]
                arows = []
                for r in adj_rows:
                    is_net = "NET" in r[0].upper()
                    style  = S("adj_bold", fontSize=8, leading=12,
                               textColor=C_BLUE if is_net else C_TEXT,
                               fontName="Helvetica-Bold" if is_net else "Helvetica")
                    arows.append([Paragraph(_tc(r[0], 120), style),
                                  Paragraph(_tc(r[1],  20), sBo),
                                  Paragraph(_tc(r[2] if len(r) > 2 else "", 250), sN)])
                at = Table([ahdr]+arows, colWidths=[W*0.50, W*0.15, W*0.35])
                at.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),C_BG),
                    ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#F0F4FF")),
                    ("LINEBELOW",(0,0),(-1,-1),0.5,C_BORDER),
                    ("BOX",(0,0),(-1,-1),1,C_BORDER),
                    ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ]))
                sec_items.append(at)
                sec_items.append(Spacer(1, 4))

            # Rental yield table (Step 5b)
            if yield_rows:
                yhdr  = [Paragraph(h, S(f"yh{i}", fontSize=7, leading=10, textColor=C_MUTED, fontName="Helvetica-Bold"))
                         for i, h in enumerate(["SCENARIO","MONTHLY RENT","ANNUAL RENT","CAPITAL VALUE","GROSS YIELD"])]
                yrows = [[Paragraph(c, sBo if i==0 else (S("yg", fontSize=8, leading=12,
                                    textColor=colors.HexColor("#1A7A4A"), fontName="Helvetica-Bold") if i==4 else sN))
                          for i, c in enumerate(r)] for r in yield_rows]
                yt = Table([yhdr]+yrows, colWidths=[W*0.12, W*0.22, W*0.22, W*0.22, W*0.22])
                yt.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),C_BG),
                    ("LINEBELOW",(0,0),(-1,-1),0.5,C_BORDER),
                    ("BOX",(0,0),(-1,-1),1,C_BORDER),
                    ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ]))
                sec_items.append(yt)
                if note_text:
                    nt = Table([[Paragraph(note_text, sN)]], colWidths=[W])
                    nt.setStyle(TableStyle([
                        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#ECFDF5")),
                        ("BOX",(0,0),(-1,-1),1,colors.HexColor("#6EE7B7")),
                        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
                    ]))
                    sec_items.append(nt)
                sec_items.append(Spacer(1, 4))
            content = ""  # skip default content block

        # ── Section F: risk & due diligence bullets ─────────────
        elif letter == "F":
            risks = sec.get("risk_points", [])
            if risks:
                _strip    = "•- "
                risk_text = "<br/><br/>".join(
                    f"• {_tc(r.lstrip(_strip), 600)}"
                    for r in risks[:5] if r.strip()
                )
                # Use Paragraph (not single-row Table) so content can flow across pages
                sec_items.append(Paragraph(risk_text, sCont))
                content = ""

        # ── Content paragraph (A, B, C LLM text, E opinion, G disclaimer) ──
        if content:
            if is_E:
                # Section E keeps Table wrapper for the blue background.
                # Replace \n with <br/> so sanity checks render on separate lines.
                ct = Table([[Paragraph(content.replace("\n", "<br/>"), sN)]], colWidths=[W])
                ct.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,-1),C_LIGHT),
                    ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
                    ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
                    ("BOX",(0,0),(-1,-1),1,C_BLUE),
                ]))
                sec_items.append(ct)
            else:
                # Use Paragraph directly — it can split across pages, eliminating
                # the large whitespace gaps caused by unsplittable single-row Tables.
                # Convert \n to <br/> so bullet points render on separate lines.
                sec_items.append(Paragraph(content.replace("\n", "<br/>"), sCont))

        # Section G: keep header + disclaimer body on the same page
        if letter == "G":
            story.append(KeepTogether(sec_items))
        else:
            story.extend(sec_items)
        story.append(Spacer(1, 4))

    # ── COMPARABLES SECTION INTENTIONALLY REMOVED ────────────────
    # The "Comparable Pricing References" section has been removed.
    # report.comparables is always [] from the engine.

    # ── FOOTER NOTE ──────────────────────────────────────────────
    story.append(HRFlowable(width=W, color=C_BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"valUProp.in | {ref} | {date_str} | "
        "Not a statutory or bank-certified valuation", sMu))

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(LM, 12*mm, f"{ref} | {date_str} | valUProp.in")
        canvas.drawRightString(PAGE_W-RM, 12*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

# ═══════════════════════════════════════════════════════════════════
# WEASYPRINT HTML FALLBACK (kept for reference)
# ═══════════════════════════════════════════════════════════════════
def _build_html(report: dict, area: dict, val_id: int) -> str:
    locality  = area.get("locality", "")
    city      = area.get("city", "")
    address   = area.get("address", f"{locality}, {city}")
    prop_type = _type_label(area.get("type", "Property"))
    date_str  = datetime.now().strftime("%d %b %Y")
    ref       = f"VUP-{val_id:05d}"
    vmin      = report.get("value_min", 0)
    vmax      = report.get("value_max", 0)
    conf      = report.get("confidence_score", 70)
    val_range = f"{_fmt(vmin)} – {_fmt(vmax)}"
    conf_color  = SUCCESS if conf >= 70 else (WARNING if conf >= 50 else DANGER)
    conf_label  = "Good" if conf >= 80 else ("Moderate" if conf >= 60 else "Low — Consult a Professional")
    sections    = report.get("sections", {})

    sec_html = ""
    for letter in ["A","B","C","D","E","F","G"]:
        sec_html += _render_section(letter, sections.get(letter, {}))

    # Comparable Pricing References section intentionally removed
    comp_html = ""

    conf_warn = ""
    if conf < 70:
        conf_warn = f"""<div class="conf-warn">
          ⚠️ Confidence score is below 70%. We recommend consulting a registered valuer
          before making any financial decisions on this property.
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<style>{_main_css()}</style></head><body>
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
  {sec_html}
  {comp_html}
  <div class="page-footer">
    <span>valUProp.in · AI-Powered Property Valuation · India</span>
    <span>{ref} · {date_str}</span>
    <span>Not a statutory or bank-certified valuation</span>
  </div>
</body></html>"""


def _render_section(letter: str, sec: dict) -> str:
    if not sec:
        return ""
    title   = sec.get("title", f"Section {letter}")
    content = sec.get("content", "")
    data_rows = ""
    if letter == "C":
        items = [("Land Rate Range",sec.get("land_rate_range","")),
                 ("Apartment Rate",sec.get("apt_rate_range","")),
                 ("Guideline Value",sec.get("guideline_value",""))]
        rows = "".join(f'<tr><td class="dt-key">{k}</td><td class="dt-val">{v}</td></tr>'
                       for k,v in items if v)
        if rows: data_rows = f'<table class="data-table">{rows}</table>'
    elif letter == "D":
        items = [("Land Value",sec.get("land_value","")),
                 ("Building Value (Depr.)",sec.get("building_value","")),
                 ("Location Adjustments",sec.get("adjustments",""))]
        rows = "".join(f'<tr><td class="dt-key">{k}</td><td class="dt-val">{v}</td></tr>'
                       for k,v in items if v)
        if rows: data_rows = f'<table class="data-table">{rows}</table>'
    elif letter == "E":
        vr = sec.get("value_range","")
        if vr: data_rows = f'<div class="opinion-range">{vr}</div>'
    elif letter == "F":
        risks = sec.get("risk_points",[])
        if risks:
            items_html = "".join(f'<li class="risk-item"><span class="risk-bullet">•</span>{r.lstrip("•- ")}</li>'
                                 for r in risks if r.strip())
            data_rows = f'<ul class="risk-list">{items_html}</ul>'
            content = ""
    is_opinion    = letter == "E"
    is_disclaimer = letter == "G"
    card_style = 'style="border-color:#1B3F6E;background:#EBF3FF;"' if is_opinion else \
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


def _main_css() -> str:
    return f"""
    @page {{ size: A4; margin: 18mm 16mm 22mm 16mm; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: #18202E; line-height: 1.55; }}
    .page-header {{ display: flex; justify-content: space-between; align-items: flex-start; background: {BRAND_BLUE}; color: white; padding: 14px 18px; border-radius: 8px; margin-bottom: 14px; }}
    .header-brand {{ display: flex; align-items: center; gap: 12px; }}
    .header-shield {{ width: 36px; height: 36px; border-radius: 8px; background: rgba(255,255,255,0.15); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
    .header-logo {{ font-size: 20pt; font-weight: 700; color: white; }}
    .header-subtitle {{ font-size: 8.5pt; opacity: 0.7; margin-top: 2px; }}
    .header-meta {{ font-size: 8.5pt; opacity: 0.8; text-align: right; line-height: 1.8; }}
    .value-banner {{ background: #EBF3FF; border: 1.5px solid {BRAND_BLUE}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; display: flex; gap: 20px; justify-content: space-between; }}
    .banner-label {{ font-size: 7.5pt; font-weight: 700; letter-spacing: 0.8px; color: {BRAND_BLUE}; margin-bottom: 5px; }}
    .banner-address {{ font-size: 11pt; font-weight: 600; color: #111827; }}
    .banner-value {{ font-size: 22pt; font-weight: 700; color: {BRAND_BLUE}; margin-bottom: 3px; }}
    .banner-sub {{ font-size: 8pt; color: #6B7280; margin-bottom: 8px; }}
    .banner-value-block {{ text-align: right; }}
    .conf-badge {{ display: inline-block; color: white; font-size: 8.5pt; font-weight: 600; padding: 3px 12px; border-radius: 20px; }}
    .conf-warn {{ background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 6px; padding: 10px 14px; font-size: 9pt; color: #78350F; margin-bottom: 12px; }}
    .section-card {{ border: 1px solid #E0E4EC; border-radius: 8px; margin-bottom: 10px; overflow: hidden; page-break-inside: avoid; }}
    .section-head {{ display: flex; align-items: center; gap: 10px; background: #F6F7FA; padding: 9px 14px; border-bottom: 1px solid #E0E4EC; }}
    .sec-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 6px; background: {BRAND_BLUE}; color: white; font-size: 10pt; font-weight: 700; flex-shrink: 0; }}
    .sec-title {{ font-size: 10.5pt; font-weight: 700; color: #111827; }}
    .section-body {{ padding: 12px 14px; }}
    .sec-content {{ font-size: 9.5pt; color: #374151; line-height: 1.65; margin-top: 8px; }}
    .data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
    .dt-key {{ font-size: 9pt; color: #6B7280; padding: 5px 0; border-bottom: 1px solid #F3F4F6; width: 55%; }}
    .dt-val {{ font-size: 9pt; color: #111827; font-weight: 600; padding: 5px 0; border-bottom: 1px solid #F3F4F6; text-align: right; }}
    .opinion-range {{ font-size: 18pt; font-weight: 700; color: {BRAND_BLUE}; margin-bottom: 8px; }}
    .risk-list {{ list-style: none; padding: 0; margin: 0; }}
    .risk-item {{ display: flex; gap: 8px; align-items: flex-start; padding: 5px 0; border-bottom: 1px solid #F3F4F6; font-size: 9.5pt; color: #374151; }}
    .risk-bullet {{ color: {BRAND_ACCENT}; font-size: 12pt; line-height: 1.2; flex-shrink: 0; }}
    .page-footer {{ position: fixed; bottom: -14mm; left: 0; right: 0; display: flex; justify-content: space-between; font-size: 7.5pt; color: #9CA3AF; padding: 6px 16mm; border-top: 1px solid #E0E4EC; }}
    """


def _watermark_css() -> str:
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
        return "-"
    if lakhs >= 100:
        return f"Rs.{lakhs/100:.2f} Cr"
    return f"Rs.{lakhs:.1f} L"

def _type_label(t: str) -> str:
    return {
        "Apartment":        "Apartment / Flat",
        "IndependentHouse": "Independent House",
        "Villa":            "Villa",
        "LandPlot":         "Land / Plot",
    }.get(t, t)
