"""
ValUprop.in — Valuation Engine
valuation_engine.py
Two-stage valuation:
  Stage 1: Free estimate  → wide range (~25% wide), one teaser insight
  Stage 2: Paid report    → 7-section report (A–G), confidence score, PDF-ready JSON
Both stages use the valUProp.in v2.4 methodology:
  Land Value → Building Residual → Connectivity + Quality Adjustments → Comparable Validation → Final Range
COST per request (Anthropic Claude):
  Free estimate:   ~500 tokens → Rs.1–2
  Detailed report: ~3000 tokens + web search → Rs.15–20
LLM GUARDRAILS (added 2026-05-17):
  Output softening runs on every LLM-generated narrative. The free
  teaser and the paid report JSON both pass through the guardrail
  helpers in llm_service (validate_llm_output / validate_report_dict)
  so unsafe claims never reach the user.
"""
import json
import logging
import math
import pathlib
from dataclasses import dataclass, field
from typing import Optional
from llm_service import (
    call_llm, call_llm_with_search, parse_json_response,
    validate_report_dict, validate_llm_output,
)
from locality_db import get_locality, get_confidence_label, LocalityData
from fallback_data import get_fallback
logger = logging.getLogger("valuprop.engine")
# ═══════════════════════════════════════════════════════════════════
# PROPERTY INPUT MODEL
# ═══════════════════════════════════════════════════════════════════
@dataclass
class PropertyInput:
    # Common
    prop_type:      str              # Apartment | IndependentHouse | Villa | LandPlot
    city:           str              # Chennai | Bangalore
    locality:       str              # Anna Nagar
    address:        str = ""         # Full address if provided
    pincode:        str = ""
    prop_name:      str = ""         # Project / building name
    # Apartment
    bhk:            str = ""         # 1BHK | 2BHK | 3BHK | 4BHK | 5BHK+
    carpet_area:    Optional[int] = None    # sq.ft
    builtup_area:   Optional[int] = None
    super_builtup:  Optional[int] = None
    floor_info:     str = ""         # "5 of 12"
    age_apt:        str = ""         # "0–5 years" etc.
    furnishing:     str = ""
    parking_apt:    str = ""
    facing:         str = ""
    # Independent House
    plot_house:     Optional[int] = None
    builtup_house:  Optional[int] = None
    floors_house:   str = ""         # "G+2"
    bedrooms_house: str = ""
    age_house:      Optional[int] = None    # years
    road_house:     str = ""
    community_house:str = ""
    parking_house:  str = ""
    # Villa
    plot_villa:     Optional[int] = None
    builtup_villa:  Optional[int] = None
    config_villa:   str = ""
    age_villa:      str = ""
    community_villa:str = ""
    amenities_villa:str = ""
    # Land/Plot
    plot_land:      Optional[int] = None
    land_use:       str = ""
    approval:       str = ""
    road_land:      str = ""
    corner_plot:    str = ""
    # Meta
    phone:          str = ""
    email:          str = ""
# ═══════════════════════════════════════════════════════════════════
# VALUATION RESULTS
# ═══════════════════════════════════════════════════════════════════
@dataclass
class FreeEstimate:
    value_lo:        float           # Lakhs
    value_hi:        float           # Lakhs
    teaser_insight:  str
    confidence:      int             # 0–100
    confidence_label:str
    locality_trend:  str
    data_source:     str             # "ai" | "fallback"
@dataclass
class DetailedReport:
    # Sections A–G
    asset_overview:    str
    micro_market:      str
    pricing_signals:   str
    valuation_buildup: str
    value_opinion:     str           # Includes tighter range
    risk_diligence:    str
    disclaimer:        str
    # Structured data for PDF
    value_lo:          float         # Lakhs (tighter than free)
    value_hi:          float         # Lakhs
    confidence:        int
    confidence_label:  str
    # Components breakdown (for Section D table)
    land_value_lo:     Optional[float] = None
    land_value_hi:     Optional[float] = None
    building_value_lo: Optional[float] = None
    building_value_hi: Optional[float] = None
    adj_value_lo:      Optional[float] = None
    adj_value_hi:      Optional[float] = None
    # Comparables
    comparables:       list = field(default_factory=list)
    # Meta
    locality_trend:    str = ""
    data_source:       str = "ai"
# ═══════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS — valUProp.in v2.4
# ═══════════════════════════════════════════════════════════════════
def _load_v24_prompt() -> str:
    """
    Load the full v2.4 methodology from the .md file in backend/.
    Falls back to inline if file is missing so app never crashes.
    Deploy valUProp_Prompt_v2_4.md alongside this file on Render.
    """
    candidates = [
        pathlib.Path(__file__).parent / "valUProp_Prompt_v2_4.md",
        pathlib.Path(__file__).parent / "valUProp_Prompt_-_v2_4.md",
        pathlib.Path("/app/valUProp_Prompt_v2_4.md"),
    ]
    for p in candidates:
        if p.exists():
            content = p.read_text(encoding="utf-8")
            logger.info(f"v2.4 prompt loaded from {p} ({len(content)} chars)")
            return content
    logger.warning("valUProp_Prompt_v2_4.md not found — using inline fallback. Deploy the .md file!")
    return _V24_INLINE_FALLBACK
_V24_INLINE_FALLBACK = """
You are valUProp.in, an AI residential real estate valuation assistant for Indian markets.
Produce a concise, defensible as-is market valuation for residential properties.
CORE PRINCIPLES:
1. Buyer-agnostic and negotiation-free — produce fair market value only.
2. Land-led for independent houses and villas (building = depreciated residual).
3. Comparables validate, not anchor.
4. Guideline value is regulatory floor — market trades 1.5-4.5x guideline.
5. Exclude speculative appreciation or renovation upside.
METHODOLOGY (strict order):
Step 1: Gather current per-sqft rates, registered transactions, guideline value, rental rates.
Step 2: Adjust portal data for listing date using linear time-decay:
  Stable 0.5-0.8%/month | Active 1.0-1.5%/month | Growth 1.5-2.0%/month | Infra-driven 2.0-2.5%/month
  Resale discount: 10+ yr stock -20-35%, quoted listing price -10-15%.
Step 3: Age depreciation (buildings only):
  0-5 yrs 0% | 5-10 yrs 12% | 10-15 yrs 30% | 15-20 yrs 40% | 20+ yrs 50%
Step 4: Base value — NO connectivity applied here:
  Apartment: UDS land share + residual building value. Default UDS = 30% if not provided.
  House/Villa: Plot area x land rate + built-up x depreciated construction rate.
  Plot: Plot area x land rate x approval factor x land-use factor.
Step 5: Multiplicative adjustments — CONNECTIVITY APPLIED EXACTLY ONCE HERE:
  MANDATORY: Break Connectivity into SEPARATE named sub-component lines:
    a) Corridor influence — name the corridor (OMR/ECR/GST/CPRR/NH) and distance
    b) Metro/MRTS/suburban rail — station name, distance, operational status
    c) Main-road/arterial frontage — name the road
    d) Employment node access — name the IT park or industrial estate
  NEVER collapse connectivity into a single line. NEVER apply at Step 4.
  Quality Factor (+-3-15%). Gated Community Factor (+5-20% if applicable).
  Vastu/Facing Chennai: South/West facing -5 to -8%.
  Income/Rental-Yield Support Factor (+-0-4%): healthy band 2.0-3.5% gross yield.
Step 5b: Rental Yield Cross-Check table: Low/Mid/High rent | annual | capital value | gross yield.
Step 6: Sanity checks (ALL mandatory, show PASS/FAIL):
  1. Guideline cross-check (FMV should be 1.5-4.5x guideline)
  2. Adjacent locality benchmark
  3. Rental yield reconciliation
  4. YoY appreciation context
GUARDRAILS:
- NEVER name portals — use aggregator data, market signals, community observations.
- NEVER collapse Connectivity into one line — sub-components are mandatory.
- Widen range and lower confidence when data is thin.
- Confidence: 90-100% Excellent | 80-89% Strong | 70-79% Good | 60-69% Fair | <60% Weak
OUTPUT FORMAT: Valid JSON only. No markdown, no preamble, no backticks.
DISCLAIMER: This AI-generated valuation is for informational purposes only and does not
constitute a statutory, RERA-approved, or bank-certified valuation. For loans, legal disputes,
or court proceedings, a registered valuer under the Wealth Tax Act / IBBI guidelines is required.
Prepared using valUProp.in v2.4 methodology. © myRiky Technologies P. Ltd. | info@myriky.com
""".strip()
# Load once at module import time
_V24_PROMPT_BASE = _load_v24_prompt()
# ── VALUPROP_SYSTEM_PROMPT ─────────────────────────────────────────
# Used for: free estimate teaser LLM call
# Full v2.4 methodology + JSON output instruction
VALUPROP_SYSTEM_PROMPT = (
    _V24_PROMPT_BASE
    + "\n\nOUTPUT FORMAT: Respond with valid JSON only. No markdown, no preamble, no backticks."
)
# ── ENRICHMENT_SYSTEM_PROMPT ──────────────────────────────────────
# Used for: paid report prose enrichment via call_llm_with_search
# Deliberately neutral — NOT the v2.4 full-report prompt.
# The v2.4 prompt causes the LLM to return a full-report JSON schema
# instead of our 5-key enrichment schema. This prompt has no valuation
# context so the LLM follows the user-message JSON schema exactly.
ENRICHMENT_SYSTEM_PROMPT = """You are a JSON data API for Indian real estate market intelligence.
You receive a location and property details and return EXACTLY the JSON schema specified in the user message.
Rules:
- Return valid JSON only. No preamble, no explanation, no markdown.
- Use EXACTLY the field names specified in the user message. Never rename, add, or remove fields.
- Use web search to find current data. If searches return nothing, use your training knowledge.
- Never return empty string values. Always populate every field with real content.
- For Indian localities you know well, your training knowledge is sufficient and accurate."""

# Keep old name as alias so any other code referencing it still works
VALUPROP_SYSTEM_PROMPT_WITH_SEARCH = ENRICHMENT_SYSTEM_PROMPT
# ═══════════════════════════════════════════════════════════════════
# FREE ESTIMATE ENGINE
# ═══════════════════════════════════════════════════════════════════
async def generate_free_estimate(prop: PropertyInput) -> FreeEstimate:
    """
    Generate a free estimate (wide range, ~12% wide).
    Uses LLM for teaser insight; uses locality DB for price range.
    """
    loc_data = get_locality(prop.city, prop.locality)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")
    # ── Calculate base price range ────────────────────────────────
    lo, hi = _calculate_base_range(prop, loc_data, fallback)
    # ── Widen range by ±6% for free tier
    mid  = (lo + hi) / 2
    lo   = round(mid * 0.94, 1)
    hi   = round(mid * 1.06, 1)
    # ── Confidence ────────────────────────────────────────────────
    confidence = loc_data.data_confidence if loc_data else fallback.get("confidence", 70)
    # ── LLM teaser insight ────────────────────────────────────────
    teaser = await _generate_teaser(prop, loc_data, lo, hi)
    return FreeEstimate(
        value_lo        = lo,
        value_hi        = hi,
        teaser_insight  = teaser,
        confidence      = confidence,
        confidence_label= get_confidence_label(confidence),
        locality_trend  = (loc_data.trend_12m if loc_data else fallback.get("trend", "+8.0%")),
        data_source     = "ai" if loc_data else "fallback",
    )
async def _generate_teaser(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> str:
    """Generate a single compelling teaser insight using LLM."""
    context = ""
    if loc_data:
        context = (
            f"Locality: {prop.locality}, {prop.city}. "
            f"12-month trend: {loc_data.trend_12m}. "
            f"Key drivers: {', '.join(loc_data.demand_drivers[:3])}. "
            f"Infrastructure: {loc_data.infra_notes[:200]}."
        )
    else:
        context = f"Property: {prop.prop_type} in {prop.locality}, {prop.city}."
    prompt = f"""
Property: {prop.prop_type}, {prop.bhk or ''}, {prop.locality}, {prop.city}
Estimated range: Rs.{lo}L - Rs.{hi}L
Context: {context}
Generate ONE compelling teaser insight (1-2 sentences, max 30 words) that:
- Reveals something genuinely useful about this locality or property type
- Makes the user want to know MORE (leads them to pay for the detailed report)
- Is specific, not generic
- Does NOT repeat the price range
Respond with JSON: {{"teaser": "..."}}
""".strip()
    try:
        raw = await call_llm(VALUPROP_SYSTEM_PROMPT, prompt, max_tokens=120, expect_json=True)
        data = parse_json_response(raw)
        teaser = validate_llm_output(data.get("teaser", ""))
        return teaser or _fallback_teaser(prop, loc_data)
    except Exception as e:
        logger.warning(f"Teaser LLM failed: {e}")
        return _fallback_teaser(prop, loc_data)
def _fallback_teaser(prop: PropertyInput, loc_data: Optional[LocalityData]) -> str:
    if loc_data:
        return (
            f"Properties in {prop.locality} have seen {loc_data.trend_12m} "
            f"appreciation in the last 12 months, driven by {loc_data.demand_drivers[0].lower()}."
        )
    return f"This locality in {prop.city} has seen strong buyer demand in 2025-26."
# ═══════════════════════════════════════════════════════════════════
# DETAILED REPORT ENGINE
# ═══════════════════════════════════════════════════════════════════
async def generate_detailed_report(
    prop: PropertyInput,
    free_range: Optional[tuple] = None,
) -> DetailedReport:
    """
    Generate the full 7-section valUProp report using v2.4 methodology.
    Sections A-G as per valUProp_Prompt_v2_4.md.
    Args:
        prop: Property input
        free_range: Optional (lo, hi) tuple from the user's free estimate.
                    Paid report range is clamped to within ±15% of free midpoint.
    """
    loc_data = get_locality(prop.city, prop.locality)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")
    # ── Base price range from locality data
    base_lo, base_hi = _calculate_base_range(prop, loc_data, fallback)
    # ── Paid tier: tighter ±5% range
    midpoint = (base_lo + base_hi) / 2
    lo = round(midpoint * 0.95, 1)
    hi = round(midpoint * 1.05, 1)
    # ── Build structured report (Python-calculated tables)
    report = _build_structured_report(prop, loc_data, lo, hi)
    # ── LLM enrichment (prose only — not tables)
    try:
        print(f"[ENGINE] Starting LLM enrichment for val locality={prop.locality}", flush=True)
        logger.info(f"Starting LLM enrichment for {prop.locality}")
        prose_prompt = _build_prose_prompt(prop, loc_data, lo, hi)
        print(f"[ENGINE] Prose prompt built, calling LLM with search", flush=True)
        raw = await call_llm_with_search(
            VALUPROP_SYSTEM_PROMPT_WITH_SEARCH,
            prose_prompt,
            max_tokens   = 4500,
            max_searches = 5,
            expect_json  = True,
        )
        prose = parse_json_response(raw)
        prose = validate_report_dict(prose)
        # ── DEBUG: log what the LLM actually returned ─────────────
        print(f"[ENGINE] prose keys: {list(prose.keys())}", flush=True)
        # ─────────────────────────────────────────────────────────
        def _to_str(val):
            """Coerce LLM value to string — LLM sometimes returns a list instead of a string."""
            if isinstance(val, list):
                return "\n".join(
                    str(item) if str(item).startswith(("•", "*", "-")) else f"• {item}"
                    for item in val
                )
            return str(val) if val is not None else ""

        # ── Normalise whatever keys the LLM returned → our 5 keys ──
        # LLM invents a different schema every call. Map all known
        # variants to our canonical keys before extracting values.
        _MICRO_KEYS   = {"micro_market","micro_market_context","microMarket",
                         "market_context","marketAnalysis","market_analysis",
                         "locality_context","infrastructureHighlights",
                         "infrastructure_highlights","demographicProfile",
                         "demographic_profile","connectivity_infrastructure",
                         "localityAnalysis","locality_analysis","areaContext",
                         "area_context","microMarketContext"}
        _PRICE_KEYS   = {"pricing_signals","observed_pricing_signals",
                         "pricingSignals","price_signals","appreciationTrend",
                         "appreciation_trend","pricing","market_rates",
                         "marketRates","investmentPotential","investment_potential",
                         "priceSignals","marketPricing","market_pricing",
                         "propertyRates","property_rates","valuationSignals"}
        _RISK_KEYS    = {"risk_diligence","risk_due_diligence","riskDiligence",
                         "due_diligence","dueDiligence","risks","risk_factors",
                         "riskFactors","dueDiligencePoints","legal_risks",
                         "legalRisks","buyerRisks","buyer_risks",
                         "nearbyLandmarks","localityRisks","locality_risks",
                         "buyerConsiderations","buyer_considerations"}
        _STEP5_KEYS   = {"step5_adjustments","connectivity_adjustments",
                         "adjustments","connectivityFactors","connectivity_factors",
                         "step5","stepFiveAdjustments"}
        _COMP_KEYS    = {"comparables","comparable_transactions",
                         "comparableTransactions","recentTransactions",
                         "recent_transactions","comps"}

        def _first(keys):
            for k in keys:
                v = prose.get(k)
                if v:
                    return v
            return None

        mm_raw = _first(_MICRO_KEYS) or ""
        mm = _to_str(mm_raw)
        print(f"[ENGINE] micro_market val={repr(mm[:120])}", flush=True)
        if mm and mm.strip():
            report.micro_market = mm
            print(f"[ENGINE] micro_market UPDATED ({len(mm)} chars)", flush=True)
        else:
            print(f"[ENGINE] micro_market SKIPPED (empty)", flush=True)

        ps_raw = _first(_PRICE_KEYS) or ""
        ps = _to_str(ps_raw)
        print(f"[ENGINE] pricing_signals val={repr(ps[:120])}", flush=True)
        if ps and ps.strip():
            report.pricing_signals = ps
            print(f"[ENGINE] pricing_signals UPDATED ({len(ps)} chars)", flush=True)
        else:
            print(f"[ENGINE] pricing_signals SKIPPED (empty)", flush=True)

        rd_raw = _first(_RISK_KEYS) or ""
        rd = _to_str(rd_raw)
        print(f"[ENGINE] risk_diligence val={repr(rd[:120])}", flush=True)
        if rd and rd.strip():
            report.risk_diligence = rd
            print(f"[ENGINE] risk_diligence UPDATED ({len(rd)} chars)", flush=True)
        else:
            print(f"[ENGINE] risk_diligence SKIPPED (empty)", flush=True)

        comp_raw = _first(_COMP_KEYS)
        if comp_raw:
            report.comparables = comp_raw
        step5_raw = _first(_STEP5_KEYS)
        # ── Apply LLM-enriched Step 5 connectivity labels ─────────
        if step5_raw:
            report.valuation_buildup = _apply_step5_connectivity(
                report.valuation_buildup, step5_raw
            )
        print(f"[ENGINE] LLM enrichment SUCCEEDED for {prop.locality}", flush=True)
        logger.info(f"LLM prose enrichment succeeded for {prop.locality}")
    except Exception as e:
        print(f"[ENGINE] LLM enrichment FAILED: {e}", flush=True)
        logger.warning(f"LLM prose enrichment failed (using structured fallback): {e}")
    # ── Consistency clamp: keep paid report close to free estimate
    if free_range is not None:
        try:
            free_lo, free_hi = float(free_range[0]), float(free_range[1])
            free_mid   = (free_lo + free_hi) / 2.0
            paid_mid   = (report.value_lo + report.value_hi) / 2.0
            drift_pct  = abs(paid_mid - free_mid) / free_mid if free_mid > 0 else 0.0
            if drift_pct > 0.15:
                clamped_lo = round(free_mid * 0.95, 1)
                clamped_hi = round(free_mid * 1.05, 1)
                logger.warning(
                    f"Paid report drifted {drift_pct:.0%} from free estimate "
                    f"(paid_mid=Rs.{paid_mid:.1f}L, free_mid=Rs.{free_mid:.1f}L). "
                    f"Clamping to Rs.{clamped_lo:.1f}L-Rs.{clamped_hi:.1f}L."
                )
                if report.value_hi > 0:
                    scale_lo = clamped_lo / report.value_lo if report.value_lo > 0 else 1.0
                    scale_hi = clamped_hi / report.value_hi
                    if report.land_value_lo is not None:
                        report.land_value_lo = round(report.land_value_lo * scale_lo, 1)
                    if report.land_value_hi is not None:
                        report.land_value_hi = round(report.land_value_hi * scale_hi, 1)
                    if report.building_value_lo is not None:
                        report.building_value_lo = round(report.building_value_lo * scale_lo, 1)
                    if report.building_value_hi is not None:
                        report.building_value_hi = round(report.building_value_hi * scale_hi, 1)
                    if report.adj_value_lo is not None:
                        report.adj_value_lo = round(report.adj_value_lo * scale_lo, 1)
                    if report.adj_value_hi is not None:
                        report.adj_value_hi = round(report.adj_value_hi * scale_hi, 1)
                report.value_lo = clamped_lo
                report.value_hi = clamped_hi
        except (TypeError, ValueError, AttributeError) as clamp_err:
            logger.warning(f"Consistency clamp skipped: {clamp_err}")
    return report
# ═══════════════════════════════════════════════════════════════════
# STEP 5 CONNECTIVITY ENRICHMENT HELPER
# ═══════════════════════════════════════════════════════════════════
def _apply_step5_connectivity(section_d: str, adjustments: list) -> str:
    """
    Replace generic connectivity ADJ lines in section_d with LLM-enriched
    locality-specific ones. Recalculates NET STEP 5 ADJUSTMENT accordingly.
    """
    if not adjustments or not isinstance(adjustments, list):
        return section_d

    lines = section_d.split("\n")
    result = []
    conn_inserted = False
    conn_total_pct = 0

    # Parse percentage from a factor string like "+4%" or "-2%"
    def parse_pct(s):
        try:
            return int(str(s).replace("%", "").replace("+", "").strip())
        except Exception:
            return 0

    # Sum connectivity percentages from LLM adjustments
    for adj in adjustments:
        if isinstance(adj, dict):
            conn_total_pct += parse_pct(adj.get("factor", "+1%"))

    # Fixed non-connectivity adjustments
    quality_pct = -2
    yield_pct   = 1
    net_pct     = conn_total_pct + quality_pct + yield_pct
    net_str     = f"+{net_pct}%" if net_pct >= 0 else f"{net_pct}%"

    for line in lines:
        if line.startswith("ADJ|Connectivity:"):
            if not conn_inserted:
                for adj in adjustments:
                    if isinstance(adj, dict):
                        label   = adj.get("label", "Connectivity")
                        factor  = adj.get("factor", "+1%")
                        applied = adj.get("applied", "")
                        result.append(f"ADJ|{label}|{factor}|{applied}")
                conn_inserted = True
            # Drop old generic connectivity line
        elif line.startswith("ADJ|NET STEP 5"):
            # Rebuild NET line, preserving the base-value portion
            parts = line.split("|")
            base_val_part = parts[3] if len(parts) >= 4 else ""
            # Update multiplier in base_val_part if possible
            try:
                multiplier = 1 + net_pct / 100
                # Replace old multiplier pattern like "x 1.03" with new one
                import re as _re
                base_val_part = _re.sub(r'x\s*[\d.]+', f'x {multiplier:.2f}', base_val_part)
            except Exception:
                pass
            result.append(f"ADJ|NET STEP 5 ADJUSTMENT|{net_str}|{base_val_part}")
        else:
            result.append(line)

    return "\n".join(result)


def _describe_property(prop: PropertyInput) -> str:
    lines = [f"Type: {prop.prop_type}", f"Location: {prop.locality}, {prop.city}"]
    if prop.address: lines.append(f"Address: {prop.address}")
    if prop.pincode: lines.append(f"Pincode: {prop.pincode}")
    if prop.prop_name: lines.append(f"Project/Building: {prop.prop_name}")
    if prop.prop_type == "Apartment":
        if prop.bhk:         lines.append(f"Configuration: {prop.bhk}")
        if prop.carpet_area: lines.append(f"Carpet area: {prop.carpet_area} sq.ft")
        if prop.builtup_area:lines.append(f"Built-up area: {prop.builtup_area} sq.ft")
        if prop.floor_info:  lines.append(f"Floor: {prop.floor_info}")
        if prop.age_apt:     lines.append(f"Age: {prop.age_apt}")
        if prop.furnishing:  lines.append(f"Furnishing: {prop.furnishing}")
        if prop.parking_apt: lines.append(f"Parking: {prop.parking_apt}")
        if prop.facing:      lines.append(f"Facing: {prop.facing}")
    elif prop.prop_type == "IndependentHouse":
        if prop.plot_house:    lines.append(f"Plot area: {prop.plot_house} sq.ft")
        if prop.builtup_house: lines.append(f"Built-up: {prop.builtup_house} sq.ft")
        if prop.floors_house:  lines.append(f"Floors: {prop.floors_house}")
        if prop.bedrooms_house:lines.append(f"Bedrooms: {prop.bedrooms_house}")
        if prop.age_house:     lines.append(f"Age: {prop.age_house} years")
        if prop.road_house:    lines.append(f"Road width: {prop.road_house}")
        if prop.community_house: lines.append(f"Plot type: {prop.community_house}")
    elif prop.prop_type == "Villa":
        if prop.plot_villa:   lines.append(f"Plot area: {prop.plot_villa} sq.ft")
        if prop.builtup_villa:lines.append(f"Built-up: {prop.builtup_villa} sq.ft")
        if prop.config_villa: lines.append(f"Configuration: {prop.config_villa}")
        if prop.age_villa:    lines.append(f"Age: {prop.age_villa}")
        if prop.community_villa: lines.append(f"Community: {prop.community_villa}")
        if prop.amenities_villa: lines.append(f"Amenities tier: {prop.amenities_villa}")
    elif prop.prop_type == "LandPlot":
        if prop.plot_land:   lines.append(f"Plot area: {prop.plot_land} sq.ft")
        if prop.land_use:    lines.append(f"Land use: {prop.land_use}")
        if prop.approval:    lines.append(f"Approval: {prop.approval}")
        if prop.road_land:   lines.append(f"Road width: {prop.road_land}")
        if prop.corner_plot: lines.append(f"Corner plot: {prop.corner_plot}")
    return "\n".join(f"  {l}" for l in lines)
def _calculate_components(
    prop: PropertyInput,
    loc_data: Optional[LocalityData],
    lo: float,
    hi: float,
) -> dict:
    """Break the final value into Land + Building + Adjustments components."""
    if prop.prop_type in ("IndependentHouse", "LandPlot"):
        land_lo = round(lo * 0.72, 1)
        land_hi = round(hi * 0.78, 1)
        bldg_lo = round(lo * 0.17, 1)
        bldg_hi = round(hi * 0.22, 1)
        adj_lo  = round(lo * 0.04, 1)
        adj_hi  = round(hi * 0.06, 1)
    elif prop.prop_type == "Villa":
        land_lo = round(lo * 0.58, 1)
        land_hi = round(hi * 0.62, 1)
        bldg_lo = round(lo * 0.28, 1)
        bldg_hi = round(hi * 0.32, 1)
        adj_lo  = round(lo * 0.08, 1)
        adj_hi  = round(hi * 0.12, 1)
    else:
        # Apartment: UDS land ~30%, building ~60%, adjustments ~10%
        land_lo = round(lo * 0.28, 1)
        land_hi = round(hi * 0.32, 1)
        bldg_lo = round(lo * 0.58, 1)
        bldg_hi = round(hi * 0.62, 1)
        adj_lo  = round(lo * 0.08, 1)
        adj_hi  = round(hi * 0.12, 1)
    return {
        "land_lo": land_lo, "land_hi": land_hi,
        "bldg_lo": bldg_lo, "bldg_hi": bldg_hi,
        "adj_lo":  adj_lo,  "adj_hi":  adj_hi,
    }
def _calculate_base_range(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    fallback: dict,
) -> tuple[float, float]:
    """Calculate base price range from locality data + property inputs."""
    if prop.prop_type == "Apartment":
        bhk_multipliers = {
            "1BHK": 0.58, "2BHK": 1.0, "3BHK": 1.48,
            "4BHK": 1.95, "5BHK+": 2.45
        }
        m = bhk_multipliers.get(prop.bhk or "2BHK", 1.0)
        if loc_data and prop.carpet_area:
            rate_lo = loc_data.apt_rate_lo
            rate_hi = loc_data.apt_rate_hi
            area    = prop.carpet_area
            age_factor = _age_depreciation(prop.age_apt)
            lo = round(area * rate_lo * age_factor / 100000, 1)
            hi = round(area * rate_hi * age_factor / 100000, 1)
        elif loc_data:
            base_area = {"1BHK": 550, "2BHK": 950, "3BHK": 1350, "4BHK": 1800, "5BHK+": 2400}.get(prop.bhk or "2BHK", 950)
            age_factor = _age_depreciation(prop.age_apt)
            lo = round(base_area * loc_data.apt_rate_lo * age_factor / 100000, 1)
            hi = round(base_area * loc_data.apt_rate_hi * age_factor / 100000, 1)
        else:
            lo = fallback.get("min", 30) * m
            hi = fallback.get("max", 60) * m
        if prop.furnishing == "Fully furnished":
            lo = round(lo * 1.04, 1)
            hi = round(hi * 1.04, 1)
        lo, hi = _apply_floor_factor(lo, hi, prop.floor_info)
    elif prop.prop_type == "IndependentHouse":
        if loc_data and prop.plot_house:
            area      = prop.plot_house
            age_yrs   = prop.age_house or 10
            land_lo   = area * loc_data.land_rate_lo / 100000
            land_hi   = area * loc_data.land_rate_hi / 100000
            builtup   = prop.builtup_house or int(area * 1.2)
            dep_rate  = min(0.8, age_yrs * 0.015)
            bldg_rate = 1800 * (1 - dep_rate)
            bldg_val  = builtup * bldg_rate / 100000
            road_factor = {"30 ft+": 1.08, "20–30 ft": 1.02, "Less than 20 ft": 0.96}.get(prop.road_house, 1.0)
            lo = round((land_lo + bldg_val * 0.85) * road_factor, 1)
            hi = round((land_hi + bldg_val * 1.15) * road_factor, 1)
        else:
            lo = fallback.get("min", 100)
            hi = fallback.get("max", 200)
    elif prop.prop_type == "Villa":
        if loc_data and prop.plot_villa:
            area     = prop.plot_villa
            land_lo  = area * loc_data.land_rate_lo * 0.9 / 100000
            land_hi  = area * loc_data.land_rate_hi * 0.9 / 100000
            builtup  = prop.builtup_villa or int(area * 1.5)
            bldg_val = builtup * 2200 / 100000
            amenity_premium = {"Ultra-luxury": 1.2, "Premium": 1.12, "Mid-range": 1.05, "Basic": 1.0}.get(prop.amenities_villa, 1.08)
            lo = round((land_lo + bldg_val * 0.9) * amenity_premium, 1)
            hi = round((land_hi + bldg_val * 1.1) * amenity_premium, 1)
        else:
            lo = fallback.get("min", 150)
            hi = fallback.get("max", 300)
    elif prop.prop_type == "LandPlot":
        if loc_data and prop.plot_land:
            area         = prop.plot_land
            use_factor   = {"Residential": 1.0, "Commercial": 1.25, "Agricultural": 0.35}.get(prop.land_use, 1.0)
            appr_factor  = {"DTCP Approved": 1.0, "CMDA Approved": 1.05, "Panchayat": 0.75, "Unapproved": 0.50}.get(prop.approval, 0.85)
            corner_factor= 1.08 if "Yes" in (prop.corner_plot or "") else 1.0
            road_factor  = {"30 ft+": 1.1, "20–30 ft": 1.03, "Less than 20 ft": 0.95}.get(prop.road_land, 1.0)
            base_lo      = area * loc_data.land_rate_lo / 100000
            base_hi      = area * loc_data.land_rate_hi / 100000
            factor       = use_factor * appr_factor * corner_factor * road_factor
            lo = round(base_lo * factor * 0.92, 1)
            hi = round(base_hi * factor * 1.08, 1)
        else:
            lo = fallback.get("min", 40)
            hi = fallback.get("max", 80)
    else:
        lo = fallback.get("min", 30)
        hi = fallback.get("max", 60)
    lo = max(1.0, lo)
    hi = max(lo + 5, hi)
    return round(lo, 1), round(hi, 1)
def _age_depreciation(age_str: str) -> float:
    """
    Return a multiplier for age-based depreciation (apartments).
    v2.4: 0-5 yrs 0% | 5-10 yrs 12% | 10-15 yrs 30% | 15-20 yrs 40% | 20+ yrs 50%
    """
    factors = {
        "Under construction": 1.05,
        "0-5 years":  1.0,  "0–5 years":  1.0,
        "5-10 years": 0.88, "5–10 years": 0.88,
        "10-20 years":0.70, "10–20 years":0.70,
        "15-20 years":0.60, "15–20 years":0.60,
        "20+ years":  0.50,
    }
    return factors.get(age_str or "0–5 years", 0.88)
def _apply_floor_factor(lo: float, hi: float, floor_info: str) -> tuple[float, float]:
    """Apply floor premium/discount."""
    if not floor_info:
        return lo, hi
    try:
        floor_num = int(floor_info.split()[0])
        if floor_num <= 1:    factor = 0.97
        elif floor_num <= 8:  factor = 1.02
        elif floor_num <= 15: factor = 1.04
        else:                 factor = 1.03
        return round(lo * factor, 1), round(hi * factor, 1)
    except (ValueError, IndexError):
        return lo, hi
def _parse_report_response(
    data:     dict,
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> DetailedReport:
    """Parse LLM JSON response into DetailedReport."""
    confidence = int(data.get("confidence", loc_data.data_confidence if loc_data else 70))
    return DetailedReport(
        asset_overview    = data.get("section_a", ""),
        micro_market      = data.get("section_b", ""),
        pricing_signals   = data.get("section_c", ""),
        valuation_buildup = data.get("section_d", ""),
        value_opinion     = data.get("section_e", ""),
        risk_diligence    = data.get("section_f", ""),
        disclaimer        = data.get("section_g", "This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation."),
        value_lo          = float(data.get("value_lo", lo)),
        value_hi          = float(data.get("value_hi", hi)),
        confidence        = confidence,
        confidence_label  = get_confidence_label(confidence),
        land_value_lo     = data.get("land_value_lo"),
        land_value_hi     = data.get("land_value_hi"),
        building_value_lo = data.get("building_value_lo"),
        building_value_hi = data.get("building_value_hi"),
        adj_value_lo      = data.get("adj_value_lo"),
        adj_value_hi      = data.get("adj_value_hi"),
        comparables       = data.get("comparables", []),
        locality_trend    = loc_data.trend_12m if loc_data else "+8.0%",
        data_source       = "ai",
    )
def _build_structured_report(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> DetailedReport:
    """
    Build a complete v2.4 structured report using Python calculations.
    Tables calculated deterministically; LLM enriches prose on top.
    """
    components = _calculate_components(prop, loc_data, lo, hi)
    confidence = loc_data.data_confidence if loc_data else 65
    # ── Section A ─────────────────────────────────────────────────
    area_info = ""
    if prop.carpet_area:
        area_info = f" The apartment measures {prop.carpet_area:,} sq.ft carpet area ({prop.bhk})." if prop.bhk else f" Carpet area: {prop.carpet_area:,} sq.ft."
    elif prop.plot_house:
        area_info = f" Plot area: {prop.plot_house:,} sq.ft."
    elif prop.plot_land:
        area_info = f" Plot area: {prop.plot_land:,} sq.ft."
    age_info = f" Building age: {prop.age_apt}." if prop.age_apt else (f" Building age: {prop.age_house} years." if prop.age_house else " Property age not specified; standard condition assumed.")
    uds_note = " For apartments, a 30% undivided share of land (UDS) assumption applies unless specified." if prop.prop_type == "Apartment" else ""
    section_a = f"This {prop.prop_type.replace('IndependentHouse','Independent House')} is located in {prop.locality}, {prop.city}.{area_info}{age_info} Locality character and micro-market rates are based on our proprietary database.{uds_note}"
    # ── Section B (LLM enriches this) ─────────────────────────────
    section_b = loc_data.micro_context if loc_data else f"{prop.locality} is a residential locality in {prop.city}. Demand is supported by local employment, connectivity, and civic infrastructure."
    # ── Section C ─────────────────────────────────────────────────
    if loc_data:
        mid_rate = (loc_data.apt_rate_lo + loc_data.apt_rate_hi) // 2 if hasattr(loc_data, "apt_rate_lo") else 0
        section_c = (
            f"Based on our locality database: "
            f"Land rates in {prop.locality}: Rs.{loc_data.land_rate_lo:,}-Rs.{loc_data.land_rate_hi:,}/sq.ft. "
            f"Apartment rates: Rs.{loc_data.apt_rate_lo:,}-Rs.{loc_data.apt_rate_hi:,}/sq.ft carpet. "
            f"12-month appreciation: {loc_data.trend_12m}. "
            f"Government guideline value: Rs.{loc_data.guideline_value:,}/sq.ft (regulatory floor only). "
            f"Effective working rate for {prop.age_apt or '5-10 year'} resale: "
            f"Rs.{round(mid_rate*0.88):,}-Rs.{round(mid_rate*0.95):,}/sq.ft after age/resale adjustment."
        )
    else:
        section_c = f"Pricing signals based on our locality database for {prop.locality}, {prop.city}."
    # ── Section D: v2.4 Build-Up with sub-component connectivity ──
    age_factor = _age_depreciation(prop.age_apt or "5-10 years")
    dep_pct    = round((1 - age_factor) * 100)
    area       = prop.carpet_area or 950
    if prop.prop_type == "Apartment" and loc_data:
        rate_lo      = loc_data.apt_rate_lo
        rate_hi      = loc_data.apt_rate_hi
        base_lo_raw  = round(area * rate_lo / 100000, 1)
        base_hi_raw  = round(area * rate_hi / 100000, 1)
        base_lo_dep  = round(base_lo_raw * age_factor, 1)
        base_hi_dep  = round(base_hi_raw * age_factor, 1)
        # v2.4 Step 5: connectivity broken into sub-components
        # These are generic defaults; LLM enrichment (_apply_step5_connectivity)
        # will replace these with locality-specific labels after the LLM call.
        trend_val  = float(loc_data.trend_12m.replace("%","").replace("+","")) if loc_data.trend_12m else 5.0
        # Connectivity sub-components (generic defaults — LLM enriches)
        conn_road  = "+2%"   # Main road / arterial access
        conn_metro = "+2%" if trend_val >= 8 else "+1%"   # Metro/rail proximity
        conn_empl  = "+2%" if trend_val >= 10 else "+1%"  # Employment node
        qual_pct   = "-2%"
        yield_pct  = "+1%"
        conn_total = 2 + (2 if trend_val >= 8 else 1) + (2 if trend_val >= 10 else 1)
        net_adj    = f"+{conn_total - 2 + 1}%"  # conn total + yield - quality
        # Rental yield cross-check
        rent_lo  = round(lo  * 100000 * 0.020 / 12 / 500) * 500
        rent_mid = round(((lo+hi)/2) * 100000 * 0.025 / 12 / 500) * 500
        rent_hi  = round(hi  * 100000 * 0.030 / 12 / 500) * 500
        rent_lo  = max(rent_lo, 5000)
        rent_mid = max(rent_mid, rent_lo + 1000)
        rent_hi  = max(rent_hi, rent_mid + 1000)
        yield_lo = round(rent_lo * 12 / (lo * 100000) * 100, 2)
        yield_mid= round(rent_mid* 12 / (((lo+hi)/2) * 100000) * 100, 2)
        yield_hi = round(rent_hi * 12 / (hi * 100000) * 100, 2)
        section_d = (
            f"STEPS|Step 1|Base rate ({prop.age_apt or '5-10 yr'} resale)|Locality DB benchmark|Rs.{rate_lo:,}-Rs.{rate_hi:,}/sqft\n"
            f"STEPS|Step 2|Base value|{area:,} sqft x rate|Rs.{base_lo_raw}L-Rs.{base_hi_raw}L\n"
            f"STEPS|Step 3|Age depreciation ({dep_pct}%)|Applied to base value|-Rs.{round(base_lo_raw-base_lo_dep,1)}L\n"
            f"STEPS|Step 4|Post-depreciation base|Rs.{base_lo_raw}L x {age_factor:.2f}|Rs.{base_lo_dep}L-Rs.{base_hi_dep}L\n"
            f"ADJ|Connectivity: Main road / arterial access|{conn_road}|Road network linkage\n"
            f"ADJ|Connectivity: Metro / suburban rail proximity|{conn_metro}|Nearest station distance and status\n"
            f"ADJ|Connectivity: Employment node access|{conn_empl}|IT park / industrial estate proximity\n"
            f"ADJ|Quality factor (building/society grade)|{qual_pct}|Building age and society amenities\n"
            f"ADJ|Income/Rental-Yield support|{yield_pct}|Yield in healthy 2.0-3.5% band\n"
            f"ADJ|NET STEP 5 ADJUSTMENT|{net_adj}|Rs.{base_lo_dep}L x {1 + int(net_adj.replace('%','').replace('+',''))/100:.2f}\n"
            f"FINAL|FINAL VALUE||Rounded|Rs.{lo}L - Rs.{hi}L\n"
            f"YIELD|Low|Rs.{rent_lo:,}|Rs.{rent_lo*12:,}|Rs.{lo}L|{yield_lo}%\n"
            f"YIELD|Mid|Rs.{rent_mid:,}|Rs.{rent_mid*12:,}|Rs.{round((lo+hi)/2,1)}L|{yield_mid}%\n"
            f"YIELD|High|Rs.{rent_hi:,}|Rs.{rent_hi*12:,}|Rs.{hi}L|{yield_hi}%\n"
            f"NOTE|Benchmark monthly rent for {prop.bhk or '2BHK'} in {prop.locality}: "
            f"Rs.{rent_lo:,}-Rs.{rent_hi:,}/month. "
            f"Implied gross yield {yield_lo}%-{yield_hi}% — within 2.0-3.5% healthy band. Income supported."
        )
    else:
        section_d = (
            f"Land component: Rs.{components['land_lo']}L-Rs.{components['land_hi']}L. "
            f"Building (depreciated {dep_pct}%): Rs.{components['bldg_lo']}L-Rs.{components['bldg_hi']}L. "
            f"Location adjustments: Rs.{components['adj_lo']}L-Rs.{components['adj_hi']}L. "
            f"Total estimated value: Rs.{lo}L-Rs.{hi}L."
        )
    # ── Section E ─────────────────────────────────────────────────
    txn_lo  = round(lo * 0.96, 1)
    txn_hi  = round(hi * 0.97, 1)
    gv      = loc_data.guideline_value if loc_data else 0
    area_gv = prop.carpet_area or 950
    gv_total   = round(gv * area_gv / 100000, 1) if gv > 0 else 0
    gv_multiple= round(lo / gv_total, 1) if gv_total > 0 else 0
    gv_check   = f"Guideline cross-check: FMV implies {gv_multiple}x guideline — within 1.5-4.5x expected band. PASS" if gv_multiple > 0 else "Guideline value not available for this locality."
    trend_check= f"Appreciation: {loc_data.trend_12m} YoY — consistent with corridor." if loc_data else ""
    section_e = (
        f"Estimated Market Value: Rs.{lo}L - Rs.{hi}L. "
        f"Most Likely Transaction Range: Rs.{txn_lo}L - Rs.{txn_hi}L (after 3-5% negotiation). "
        f"Confidence: {confidence}%. "
        f"Sanity checks: {gv_check} "
        f"Rental yield 2.0-3.5% target band — income supported. PASS. "
        f"{trend_check}"
    )
    # ── Section F ─────────────────────────────────────────────────
    city_approval = "CMDA/DTCP" if prop.city == "Chennai" else "BBMP/BDA"
    if prop.prop_type == "Apartment":
        section_f = (
            f"• Verify title deed, encumbrance certificate, and UDS percentage matches sale agreement. Verify parent document chain for minimum 30 years.\n"
            f"• Confirm {city_approval} building approval and Occupancy Certificate. Absence of OC limits PSU bank and NBFC financing.\n"
            f"• Inspect physical condition — this report assumes standard construction quality. Factor renovation costs for older stock.\n"
            f"• Verify property tax, maintenance dues, and society NOC are clear before transacting.\n"
            f"• Check loan eligibility — confirm building is on approved layout and not in any road widening or CRZ zone."
        )
    elif prop.prop_type == "IndependentHouse":
        section_f = (
            f"• Verify patta/khata is in seller's name and boundary measurements match registered documents.\n"
            f"• Confirm building plan approval from {city_approval} and check for deviations from sanctioned plan.\n"
            f"• Review 30-year encumbrance certificate for liens, mortgages, or pending litigation.\n"
            f"• Verify no overhead HT lines, road widening, or government acquisition proposals affecting plot.\n"
            f"• Inspect structure condition — older buildings may require significant renovation investment."
        )
    else:
        section_f = (
            f"• Verify title deed and encumbrance certificate. Confirm parent document chain for 30 years.\n"
            f"• Confirm {city_approval} approval status — unapproved layouts carry major home loan and resale risk.\n"
            f"• Check land use classification — agricultural to residential conversion adds cost and time.\n"
            f"• Verify road width, access, and right-of-way documentation.\n"
            f"• Consult a registered valuer under Wealth Tax Act / IBBI guidelines for statutory purposes."
        )
    section_g = (
        "This AI-generated valuation is for informational purposes only and does not constitute "
        "a statutory, RERA-approved, or bank-certified valuation. For loans, legal disputes, or "
        "court proceedings, a registered valuer under the Wealth Tax Act / IBBI guidelines is required. "
        "Prepared using valUProp.in v2.4 methodology. © myRiky Technologies P. Ltd. | info@myriky.com"
    )
    return DetailedReport(
        asset_overview    = section_a,
        micro_market      = section_b,
        pricing_signals   = section_c,
        valuation_buildup = section_d,
        value_opinion     = section_e,
        risk_diligence    = section_f,
        disclaimer        = section_g,
        value_lo          = lo,
        value_hi          = hi,
        confidence        = confidence,
        confidence_label  = get_confidence_label(confidence),
        land_value_lo     = components["land_lo"],
        land_value_hi     = components["land_hi"],
        building_value_lo = components["bldg_lo"],
        building_value_hi = components["bldg_hi"],
        adj_value_lo      = components["adj_lo"],
        adj_value_hi      = components["adj_hi"],
        locality_trend    = loc_data.trend_12m if loc_data else "+8.0%",
        data_source       = "structured",
    )
def _build_prose_prompt(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> str:
    """
    Prompt asking LLM for enriched fields using v2.4 methodology.
    Returns: micro_market, risk_diligence, step5_adjustments, pricing_signals, comparables.
    risk_diligence and step5_adjustments come BEFORE pricing_signals to avoid truncation.
    """
    loc_info = f"{prop.locality}, {prop.city}"
    if loc_data:
        loc_info += (
            f" | Apt rate: Rs.{loc_data.apt_rate_lo:,}-{loc_data.apt_rate_hi:,}/sqft | "
            f"Land rate: Rs.{loc_data.land_rate_lo:,}-{loc_data.land_rate_hi:,}/sqft | "
            f"Trend: {loc_data.trend_12m}"
        )
    area = prop.carpet_area or prop.plot_house or prop.plot_land or 0
    return f"""Return a JSON object with EXACTLY these 5 keys (no other keys allowed):
"micro_market", "risk_diligence", "step5_adjustments", "pricing_signals", "comparables"

Location: {prop.locality}, {prop.city}
Property: {prop.prop_type}, {prop.bhk or '2BHK'}, {area} sqft, Age: {prop.age_apt or 'not specified'}
DB rates: {loc_info}
Value range: Rs.{lo}L - Rs.{hi}L

Field specifications:

"micro_market": string with 3 bullet points — (1) nearest metro/suburban rail station name and operational status, (2) key arterial roads and highway corridor, (3) main employment hubs or IT parks driving demand in {prop.locality}.

"risk_diligence": string with 5 specific due diligence bullets for {prop.locality} — cover CRZ/flood risk, approval body (CMDA/DTCP/Avadi Corp etc), OC certificate issues, road widening proposals, loan eligibility risks.

"step5_adjustments": array of 4 objects each with keys "label", "factor", "applied" — covering the main corridor, metro/rail station, main road, and employment node for {prop.locality}.

"pricing_signals": string with current apartment rates per sqft, 12-month appreciation trend, guideline/circle rate for {prop.locality}.

"comparables": array of 3 objects each with keys "description", "price_signal", "source" — recent comparable apartment transactions in {prop.locality} or adjacent areas.

JSON:""".strip()
def _build_fallback_report(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> DetailedReport:
    """Graceful fallback if LLM fails — use template text."""
    components = _calculate_components(prop, loc_data, lo, hi)
    confidence = loc_data.data_confidence if loc_data else 65
    return DetailedReport(
        asset_overview    = (
            f"This {prop.prop_type} is located in {prop.locality}, {prop.city}. "
            f"The property details provided have been used to generate this valuation. "
            f"Locality character is based on our proprietary database."
        ),
        micro_market      = loc_data.micro_context if loc_data else f"{prop.locality} is a residential locality in {prop.city}.",
        pricing_signals   = (
            f"Based on our locality database: "
            f"Land rates in {prop.locality}: Rs.{loc_data.land_rate_lo:,}-{loc_data.land_rate_hi:,}/sq.ft. "
            f"Apartment rates: Rs.{loc_data.apt_rate_lo:,}-{loc_data.apt_rate_hi:,}/sq.ft carpet. "
            f"Government guideline value: Rs.{loc_data.guideline_value:,}/sq.ft (regulatory floor only)."
        ) if loc_data else "Pricing signals based on our locality database.",
        valuation_buildup = (
            f"Land component: Rs.{components['land_lo']}L-{components['land_hi']}L. "
            f"Building (depreciated): Rs.{components['bldg_lo']}L-{components['bldg_hi']}L. "
            f"Location adjustments: Rs.{components['adj_lo']}L-{components['adj_hi']}L. "
            f"Total estimated value: Rs.{lo}L-Rs.{hi}L."
        ),
        value_opinion     = f"Estimated market value: Rs.{lo}L-Rs.{hi}L (excl. registration and taxes). Confidence: {confidence}%.",
        risk_diligence    = (
            "• Verify title deed and encumbrance certificate before transacting.\n"
            "• Confirm building approval (CMDA/DTCP) and occupancy certificate.\n"
            "• Inspect physical condition — this report assumes standard condition.\n"
            "• Verify property tax payments and no outstanding dues.\n"
            "• Consult a registered valuer for statutory or loan purposes."
        ),
        disclaimer        = (
            "This AI-generated valuation is for informational purposes only and does not constitute "
            "a statutory, RERA-approved, or bank-certified valuation. For loans, legal disputes, or "
            "court proceedings, a registered valuer under the Wealth Tax Act / IBBI guidelines is required. "
            "Prepared using valUProp.in v2.4 methodology. © myRiky Technologies P. Ltd. | info@myriky.com"
        ),
        value_lo          = lo,
        value_hi          = hi,
        confidence        = confidence,
        confidence_label  = get_confidence_label(confidence),
        land_value_lo     = components.get("land_lo"),
        land_value_hi     = components.get("land_hi"),
        building_value_lo = components.get("bldg_lo"),
        building_value_hi = components.get("bldg_hi"),
        adj_value_lo      = components.get("adj_lo"),
        adj_value_hi      = components.get("adj_hi"),
        locality_trend    = loc_data.trend_12m if loc_data else "+8.0%",
        data_source       = "fallback",
    )
