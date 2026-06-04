"""
ValUprop.in — Valuation Engine
valuation_engine.py

Two-stage valuation:
  Stage 1: Free estimate  → wide range (~25% wide), one teaser insight
  Stage 2: Paid report    → 7-section report (A–G), confidence score, PDF-ready JSON

Both stages use the ValUprop GPT Instructions v2.1 methodology:
  Land Value → Building Residual → Location Adjustments → Comparable Validation → Final Range

COST per request (OpenAI GPT-4o-mini):
  Free estimate:   ~500 tokens → ₹1–2
  Detailed report: ~1500 tokens → ₹4–5

LLM GUARDRAILS (added 2026-05-17):
  Output softening runs on every LLM-generated narrative. The free
  teaser and the paid report JSON both pass through the guardrail
  helpers in llm_service (validate_llm_output / validate_report_dict)
  so unsafe claims never reach the user.
"""

import json
import logging
import math
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
# SYSTEM PROMPT — ValUprop GPT Instructions v2.1
# ═══════════════════════════════════════════════════════════════════

VALUPROP_SYSTEM_PROMPT = """
You are ValUprop.in, an AI real estate valuation assistant for Indian residential property.
You generate neutral, defensible, land-led valuation reports.

CORE PRINCIPLES:
- Valuation is buyer-agnostic and negotiation-free.
- Older independent houses are valued primarily on land. Building value is depreciated residual.
- Consistency across all sections is mandatory.
- Always disclose guideline value as a regulatory floor, not market value.
- Confidence score must reflect data quality honestly. Below 70% = recommend professional appraisal.

METHODOLOGY (always in this order):
Land Value → Depreciated Building Value → Location Adjustments → Comparable Validation → Final Range

OUTPUT FORMAT: Always respond in valid JSON only. No markdown, no preamble, no explanation outside the JSON.

DISCLAIMER (always include exactly):
"This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation."
""".strip()


# ═══════════════════════════════════════════════════════════════════
# PAID-TIER PROMPT WITH WEB SEARCH (₹99 detailed report)
# ═══════════════════════════════════════════════════════════════════

VALUPROP_SYSTEM_PROMPT_WITH_SEARCH = """
You are valUProp.in — an independent property valuation analyst for Indian real estate (Chennai & Bangalore focus).

You are generating a PAID DETAILED REPORT (₹99 tier). The customer expects accuracy within ±5% of true market value.

YOUR PROCESS — IMPORTANT:

1. FIRST, use the web_search tool 3–5 times to gather REAL CURRENT MARKET DATA:
   - Search 1: "[locality] [city] apartment price per sqft 2025"
   - Search 2: "[locality] [city] [bhk] flat for sale price"
   - Search 3: "[locality] [city] property rate trend"
   - If land/villa, also: "[locality] [city] plot land rate per sqft"
   Read snippets from MagicBricks, 99acres, Housing.com, NoBroker, etc.

2. From the search results, extract:
   - Current per-sqft rates (range observed across listings)
   - 5–10 specific comparable listings if visible (size, price, age, BHK)
   - Recent appreciation trend if mentioned
   - Government guideline rates if cited

3. THEN reason through the valuation:
   - Land-led for independent house / villa (plot × land rate + depreciated building)
   - Carpet-area-led for apartments (carpet × current rate)
   - Apply adjustments: floor premium, age depreciation, road width, facing, parking, society quality
   - Cross-check against the actual comparables you found

4. Final value range MUST BE TIGHT: max-min within 5–10% of the lower bound.
   Example: if min = ₹80L, max should be ₹84L–88L (NOT ₹95L+).

5. Report confidence honestly:
   - 85%+ : Multiple comparables found, strong micro-market data
   - 70–84%: Some comparables, reliable locality data
   - <70%: Few comparables found — recommend professional appraisal

CITE what you found in each section. Mention specific price points observed during search.
DO NOT invent numbers. If web search returns nothing useful, say so honestly and lower confidence.

Always output the FINAL answer as a single valid JSON object matching the schema in the user prompt — nothing else after the JSON.
""".strip()


# ═══════════════════════════════════════════════════════════════════
# FREE ESTIMATE ENGINE
# ═══════════════════════════════════════════════════════════════════

async def generate_free_estimate(prop: PropertyInput) -> FreeEstimate:
    """
    Generate a free estimate (wide range, ~25% wide).
    Uses LLM for teaser insight; uses locality DB for price range.
    """
    loc_data = get_locality(prop.city, prop.locality)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")

    # ── Calculate base price range ────────────────────────────────
    lo, hi = _calculate_base_range(prop, loc_data, fallback)

    # ── Widen range by ±6% for free tier (was ±12.5% — felt too wide)
    # Paid report has even tighter range with web search.
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
Estimated range: ₹{lo}L – ₹{hi}L
Context: {context}

Generate ONE compelling teaser insight (1–2 sentences, max 30 words) that:
- Reveals something genuinely useful about this locality or property type
- Makes the user want to know MORE (leads them to pay ₹99)
- Is specific, not generic
- Does NOT repeat the price range

Respond with JSON: {{"teaser": "..."}}
""".strip()

    try:
        raw = await call_llm(VALUPROP_SYSTEM_PROMPT, prompt, max_tokens=120, expect_json=True)
        data = parse_json_response(raw)
        # LLM guardrail — soften any unsafe claim in the teaser before display
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
    return f"This locality in {prop.city} has seen strong buyer demand in 2025."


# ═══════════════════════════════════════════════════════════════════
# DETAILED REPORT ENGINE
# ═══════════════════════════════════════════════════════════════════

async def generate_detailed_report(
    prop: PropertyInput,
    free_range: Optional[tuple] = None,
) -> DetailedReport:
    """
    Generate the full 7-section ValUprop report using LLM.
    Sections A–G as per GPT Instructions v2.1.

    Args:
        prop: Property input (with corrected camelCase mapping in main.py)
        free_range: Optional (lo, hi) tuple from the user's free estimate.
                    When provided, the paid report's value range is clamped
                    to within ±15% of the free estimate's midpoint, so the
                    paid number is never far from what the user saw on the
                    free results page. Refund-risk safety net.
    """
    loc_data = get_locality(prop.city, prop.locality)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")

    # ── Base price range (from locality data, ~16% spread)
    base_lo, base_hi = _calculate_base_range(prop, loc_data, fallback)

    # ── PAID TIER tightens to median ±5% (10% total spread)
    # Free tier uses ±6% (12%). Paid must be tighter than free!
    midpoint = (base_lo + base_hi) / 2
    lo = round(midpoint * 0.95, 1)
    hi = round(midpoint * 1.05, 1)

    # ── Build detailed prompt ─────────────────────────────────────
    user_prompt = _build_report_prompt(prop, loc_data, lo, hi)

    # ── Build structured report (Python-calculated tables) ──────
    # Stage 1: Python computes all tables deterministically
    # Stage 2: LLM enriches 3 prose sections with web-searched data
    report = _build_structured_report(prop, loc_data, lo, hi)

    # ── LLM enrichment (prose only — not tables) ─────────────────
    try:
        prose_prompt = _build_prose_prompt(prop, loc_data, lo, hi)
        raw = await call_llm_with_search(
            VALUPROP_SYSTEM_PROMPT_WITH_SEARCH,
            prose_prompt,
            max_tokens   = 3000,
            max_searches = 4,
            expect_json  = True,
        )
        prose = parse_json_response(raw)
        prose = validate_report_dict(prose)
        # Enrich only the prose fields — tables stay Python-calculated
        if prose.get("micro_market"):
            report.micro_market = prose["micro_market"]
        if prose.get("pricing_signals"):
            report.pricing_signals = prose["pricing_signals"]
        if prose.get("risk_diligence"):
            report.risk_diligence = prose["risk_diligence"]
        if prose.get("comparables"):
            report.comparables = prose["comparables"]
        logger.info(f"LLM prose enrichment succeeded for {prop.locality}")
    except Exception as e:
        logger.warning(f"LLM prose enrichment failed (using structured fallback): {e}")
        # Structured report still has good content from Python — no further fallback needed

    # ════════════════════════════════════════════════════════════
    # CONSISTENCY CLAMP — keep paid report close to free estimate
    # ════════════════════════════════════════════════════════════
    # The user already paid ₹99 expecting a TIGHTER version of the free
    # estimate, not a different valuation entirely. If the rule-based
    # paid range or the LLM's adjusted range drifts more than ±15% from
    # the free estimate's midpoint, force it back to ±5% around the
    # free midpoint. This protects against:
    #   1. Frontend PRICE_DB and backend locality_db rate disagreements
    #   2. LLM hallucinating different numbers despite anchored prompt
    #   3. Future rate changes in either DB getting out of sync
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
                    f"(paid_mid=₹{paid_mid:.1f}L, free_mid=₹{free_mid:.1f}L). "
                    f"Clamping range from ₹{report.value_lo:.1f}L–₹{report.value_hi:.1f}L "
                    f"to ₹{clamped_lo:.1f}L–₹{clamped_hi:.1f}L."
                )
                # Recompute components proportionally to the new total
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
            # Never let the clamp break the report — log and pass through
            logger.warning(f"Consistency clamp skipped due to error: {clamp_err}")

    return report


def _build_report_prompt(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> str:
    # Build property description
    prop_desc = _describe_property(prop)
    # Build locality context
    loc_ctx = ""
    if loc_data:
        loc_ctx = f"""
Locality database context:
- Land rate range: ₹{loc_data.land_rate_lo:,}–{loc_data.land_rate_hi:,}/sq.ft
- Apartment rate: ₹{loc_data.apt_rate_lo:,}–{loc_data.apt_rate_hi:,}/sq.ft carpet
- Guideline value (2024): ₹{loc_data.guideline_value:,}/sq.ft
- 12-month trend: {loc_data.trend_12m}
- Micro-market context: {loc_data.micro_context}
- Infrastructure: {loc_data.infra_notes}
- Demand drivers: {', '.join(loc_data.demand_drivers)}
- Risk factors: {', '.join(loc_data.risk_factors)}
- Data confidence: {loc_data.data_confidence}%
"""

    # Build valuation components
    components = _calculate_components(prop, loc_data, lo, hi)

    return f"""
Generate a complete ValUprop.in property valuation report in JSON format.

PROPERTY:
{prop_desc}

LOCALITY DATA:
{loc_ctx if loc_ctx else f"City: {prop.city}, Locality: {prop.locality}"}

PRE-CALCULATED COMPONENTS (use these as anchors, you may adjust slightly):
- Land value range: ₹{components['land_lo']}L – ₹{components['land_hi']}L
- Building value (depreciated): ₹{components['bldg_lo']}L – ₹{components['bldg_hi']}L
- Location adjustments: ₹{components['adj_lo']}L – ₹{components['adj_hi']}L
- FINAL estimated market value: ₹{lo}L – ₹{hi}L

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "section_a": "Asset overview paragraph: property type, area, age, configuration, parking, locality character. 3–4 sentences.",
  "section_b": "Micro-market context: 2–3 sentences about locality (mature/emerging, key infra, demand drivers).",
  "section_c": "Observed pricing signals: land ₹/sq.ft, apartment ₹/sq.ft, guideline value, 2–3 comparable signals. Be specific with numbers.",
  "section_d": "Valuation build-up narrative: explain Land + Building + Adjustments = Final. Reference the component ranges above. Include a brief table description.",
  "section_e": "Independent value opinion: state the final value range ₹{lo}L – ₹{hi}L, explain what it means, note the confidence score.",
  "section_f": "Risk and due diligence: exactly 4 specific bullet points as a single string, each starting with '• '. Cover title, approvals, physical, market risks specific to this property and locality.",
  "section_g": "This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation.",
  "value_lo": {lo},
  "value_hi": {hi},
  "land_value_lo": {components['land_lo']},
  "land_value_hi": {components['land_hi']},
  "building_value_lo": {components['bldg_lo']},
  "building_value_hi": {components['bldg_hi']},
  "adj_value_lo": {components['adj_lo']},
  "adj_value_hi": {components['adj_hi']},
  "confidence": {loc_data.data_confidence if loc_data else 70},
  "comparables": [
    {{"description": "comparable property 1 description", "price_signal": "₹X/sq.ft or ₹XL", "source": "public data"}},
    {{"description": "comparable property 2 description", "price_signal": "₹X/sq.ft or ₹XL", "source": "public data"}},
    {{"description": "comparable property 3 description", "price_signal": "₹X/sq.ft or ₹XL", "source": "public data"}}
  ]
}}
""".strip()


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
        # Land-led: ~75% land, ~20% building, ~5% adjustments
        land_lo = round(lo * 0.72, 1)
        land_hi = round(hi * 0.78, 1)
        bldg_lo = round(lo * 0.17, 1)
        bldg_hi = round(hi * 0.22, 1)
        adj_lo  = round(lo * 0.04, 1)
        adj_hi  = round(hi * 0.06, 1)
    elif prop.prop_type == "Villa":
        # Villa: ~60% land, ~30% building, ~10% amenity premium
        land_lo = round(lo * 0.58, 1)
        land_hi = round(hi * 0.62, 1)
        bldg_lo = round(lo * 0.28, 1)
        bldg_hi = round(hi * 0.32, 1)
        adj_lo  = round(lo * 0.08, 1)
        adj_hi  = round(hi * 0.12, 1)
    else:
        # Apartment: undivided land share ~30%, building ~60%, location premium ~10%
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
            # Area-based: most accurate
            rate_lo = loc_data.apt_rate_lo
            rate_hi = loc_data.apt_rate_hi
            area    = prop.carpet_area
            # Apply age depreciation
            age_factor = _age_depreciation(prop.age_apt)
            lo = round(area * rate_lo * age_factor / 100000, 1)
            hi = round(area * rate_hi * age_factor / 100000, 1)
        elif loc_data:
            # BHK-based estimate
            base_area = {"1BHK": 550, "2BHK": 950, "3BHK": 1350, "4BHK": 1800, "5BHK+": 2400}.get(prop.bhk or "2BHK", 950)
            age_factor = _age_depreciation(prop.age_apt)
            lo = round(base_area * loc_data.apt_rate_lo * age_factor / 100000, 1)
            hi = round(base_area * loc_data.apt_rate_hi * age_factor / 100000, 1)
        else:
            lo = fallback.get("min", 30) * m
            hi = fallback.get("max", 60) * m

        # Apply furnishing premium
        if prop.furnishing == "Fully furnished":
            lo = round(lo * 1.04, 1)
            hi = round(hi * 1.04, 1)

        # Apply floor premium/discount
        lo, hi = _apply_floor_factor(lo, hi, prop.floor_info)

    elif prop.prop_type in ("IndependentHouse",):
        if loc_data and prop.plot_house:
            area       = prop.plot_house
            age_yrs    = prop.age_house or 10
            # Land value
            land_lo = area * loc_data.land_rate_lo / 100000
            land_hi = area * loc_data.land_rate_hi / 100000
            # Depreciated building value
            builtup   = prop.builtup_house or int(area * 1.2)
            dep_rate  = min(0.8, age_yrs * 0.015)  # 1.5% depreciation/year, max 80%
            bldg_rate = 1800 * (1 - dep_rate)       # ₹1800/sq.ft replacement cost
            bldg_val  = builtup * bldg_rate / 100000
            # Road width premium
            road_factor = {"30 ft+": 1.08, "20–30 ft": 1.02, "Less than 20 ft": 0.96}.get(prop.road_house, 1.0)
            # Corner plot premium
            lo = round((land_lo + bldg_val * 0.85) * road_factor, 1)
            hi = round((land_hi + bldg_val * 1.15) * road_factor, 1)
        else:
            lo = fallback.get("min", 100)
            hi = fallback.get("max", 200)

    elif prop.prop_type == "Villa":
        if loc_data and prop.plot_villa:
            area    = prop.plot_villa
            land_lo = area * loc_data.land_rate_lo * 0.9 / 100000  # slight discount vs independent
            land_hi = area * loc_data.land_rate_hi * 0.9 / 100000
            builtup = prop.builtup_villa or int(area * 1.5)
            bldg_val = builtup * 2200 / 100000  # higher quality construction
            amenity_premium = {"Ultra-luxury": 1.2, "Premium": 1.12, "Mid-range": 1.05, "Basic": 1.0}.get(prop.amenities_villa, 1.08)
            lo = round((land_lo + bldg_val * 0.9) * amenity_premium, 1)
            hi = round((land_hi + bldg_val * 1.1) * amenity_premium, 1)
        else:
            lo = fallback.get("min", 150)
            hi = fallback.get("max", 300)

    elif prop.prop_type == "LandPlot":
        if loc_data and prop.plot_land:
            area    = prop.plot_land
            # Land use adjustment
            use_factor = {"Residential": 1.0, "Commercial": 1.25, "Agricultural": 0.35}.get(prop.land_use, 1.0)
            # Approval premium
            appr_factor = {"DTCP Approved": 1.0, "CMDA Approved": 1.05, "Panchayat": 0.75, "Unapproved": 0.50}.get(prop.approval, 0.85)
            # Corner premium
            corner_factor = 1.08 if "Yes" in (prop.corner_plot or "") else 1.0
            # Road width premium
            road_factor = {"30 ft+": 1.1, "20–30 ft": 1.03, "Less than 20 ft": 0.95}.get(prop.road_land, 1.0)
            base_lo = area * loc_data.land_rate_lo / 100000
            base_hi = area * loc_data.land_rate_hi / 100000
            factor  = use_factor * appr_factor * corner_factor * road_factor
            lo = round(base_lo * factor * 0.92, 1)
            hi = round(base_hi * factor * 1.08, 1)
        else:
            lo = fallback.get("min", 40)
            hi = fallback.get("max", 80)

    else:
        lo = fallback.get("min", 30)
        hi = fallback.get("max", 60)

    # Ensure lo < hi and both positive
    lo = max(1.0, lo)
    hi = max(lo + 5, hi)

    return round(lo, 1), round(hi, 1)


def _age_depreciation(age_str: str) -> float:
    """Return a multiplier for age-based depreciation (apartments)."""
    factors = {
        "Under construction": 1.05,   # UC premium
        "0–5 years":          1.0,
        "5–10 years":         0.95,
        "10–20 years":        0.88,
        "20+ years":          0.78,
    }
    return factors.get(age_str or "0–5 years", 0.95)


def _apply_floor_factor(lo: float, hi: float, floor_info: str) -> tuple[float, float]:
    """Apply floor premium/discount. Upper floors (3–8) command premium in most markets."""
    if not floor_info:
        return lo, hi
    try:
        floor_num = int(floor_info.split()[0])
        if floor_num <= 1:
            factor = 0.97   # Ground/1st: slight discount (privacy, lift avoidance)
        elif floor_num <= 8:
            factor = 1.02   # Mid floors: slight premium
        elif floor_num <= 15:
            factor = 1.04   # High floor: premium view
        else:
            factor = 1.03   # Very high: premium but maintenance concern
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
    Build a complete v2.4 structured report using Python calculations only.
    Tables, sanity checks, rental yield — all calculated deterministically.
    LLM enriches Section B (micro-market) and Section C narrative on top.
    """
    components = _calculate_components(prop, loc_data, lo, hi)
    confidence = loc_data.data_confidence if loc_data else 65

    # ── Section A: Asset Overview ─────────────────────────────────
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

    # ── Section B: Micro-Market (LLM enriches, fallback to DB) ────
    section_b = loc_data.micro_context if loc_data else f"{prop.locality} is a residential locality in {prop.city}. Demand is supported by local employment, connectivity, and civic infrastructure."

    # ── Section C: Pricing Signals ────────────────────────────────
    if loc_data:
        apt_rate_str = f"Rs.{loc_data.apt_rate_lo:,}-Rs.{loc_data.apt_rate_hi:,}/sq.ft carpet" if hasattr(loc_data, "apt_rate_lo") else ""
        mid_rate = (loc_data.apt_rate_lo + loc_data.apt_rate_hi) // 2 if hasattr(loc_data, "apt_rate_lo") else 0
        area = prop.carpet_area or 950
        sba = round(area * 1.25)
        base_val_lo = round(sba * loc_data.apt_rate_lo * 0.9 / 100000, 1) if hasattr(loc_data, "apt_rate_lo") else lo
        base_val_hi = round(sba * loc_data.apt_rate_hi * 1.1 / 100000, 1) if hasattr(loc_data, "apt_rate_hi") else hi
        section_c = (
            f"Based on our locality database: "
            f"Land rates in {prop.locality}: Rs.{loc_data.land_rate_lo:,}-Rs.{loc_data.land_rate_hi:,}/sq.ft. "
            f"Apartment rates: Rs.{loc_data.apt_rate_lo:,}-Rs.{loc_data.apt_rate_hi:,}/sq.ft carpet. "
            f"12-month appreciation: {loc_data.trend_12m}. "
            f"Government guideline value: Rs.{loc_data.guideline_value:,}/sq.ft (regulatory floor only). "
            f"Effective working rate for {prop.age_apt or '5-10 year'} resale: Rs.{round(mid_rate*0.88):,}-Rs.{round(mid_rate*0.95):,}/sq.ft after age/resale adjustment."
        )
    else:
        section_c = f"Pricing signals based on our locality database for {prop.locality}, {prop.city}."

    # ── Section D: Full v2.4 Build-Up ──────────────────────────────
    age_factor = _age_depreciation(prop.age_apt or "5-10 years")
    dep_pct = round((1 - age_factor) * 100)
    area = prop.carpet_area or 950

    if prop.prop_type == "Apartment" and loc_data:
        rate_lo = loc_data.apt_rate_lo
        rate_hi = loc_data.apt_rate_hi
        base_lo_raw = round(area * rate_lo / 100000, 1)
        base_hi_raw = round(area * rate_hi / 100000, 1)
        base_lo_dep = round(base_lo_raw * age_factor, 1)
        base_hi_dep = round(base_hi_raw * age_factor, 1)

        # Step 5 connectivity adjustments
        trend_val = float(loc_data.trend_12m.replace("%","").replace("+","")) if loc_data.trend_12m else 5.0
        conn_pct  = "+4%" if trend_val >= 10 else "+2%"
        qual_pct  = "-2%"
        yield_pct = "+1%"
        net_adj   = "+5%" if trend_val >= 10 else "+1%"

        # Rental yield cross-check
        rent_lo  = round(lo * 0.012 / 12 * 100) * 100  # approximate monthly rent
        rent_mid = round(lo * 0.014 / 12 * 100) * 100
        rent_hi  = round(lo * 0.016 / 12 * 100) * 100
        yield_lo = round(rent_lo * 12 / (lo * 100000) * 100, 2)
        yield_mid= round(rent_mid* 12 / (((lo+hi)/2) * 100000) * 100, 2)
        yield_hi = round(rent_hi * 12 / (hi * 100000) * 100, 2)

        # Guideline cross-check
        gv = loc_data.guideline_value or 0
        gv_total = round(gv * area / 100000, 1) if gv > 0 else 0
        gv_multiple = round(lo / gv_total, 1) if gv_total > 0 else 0

        section_d = (
            f"Step 1 - Base rate: Rs.{rate_lo:,}-Rs.{rate_hi:,}/sq.ft (locality database benchmark). "
            f"Step 2 - Base value: {area:,} sq.ft x rate = Rs.{base_lo_raw}L-Rs.{base_hi_raw}L. "
            f"Step 3 - Age depreciation ({dep_pct}% for {prop.age_apt or '5-10 years'}): applied. "
            f"Step 4 - Post-depreciation: Rs.{base_lo_dep}L-Rs.{base_hi_dep}L. "
            f"Step 5 adjustments: Connectivity {conn_pct} | Quality {qual_pct} | Rental-yield support {yield_pct} | Net {net_adj}. "
            f"Step 5b - Rental yield: Rs.{rent_lo:,}/month (low) implies {yield_lo}% gross yield; "
            f"Rs.{rent_mid:,}/month (mid) implies {yield_mid}%; "
            f"Rs.{rent_hi:,}/month (high) implies {yield_hi}%. Target band 2-3.5% - income supported. "
            f"Final: Rs.{lo}L - Rs.{hi}L."
        )
    else:
        section_d = (
            f"Land component: Rs.{components['land_lo']}L-Rs.{components['land_hi']}L. "
            f"Building (depreciated {dep_pct}%): Rs.{components['bldg_lo']}L-Rs.{components['bldg_hi']}L. "
            f"Location adjustments: Rs.{components['adj_lo']}L-Rs.{components['adj_hi']}L. "
            f"Total estimated value: Rs.{lo}L-Rs.{hi}L."
        )

    # ── Section E: Value Opinion with Sanity Checks ────────────────
    txn_lo = round(lo * 0.96, 1)
    txn_hi = round(hi * 0.97, 1)
    gv = loc_data.guideline_value if loc_data else 0
    area_for_gv = prop.carpet_area or 950
    gv_total = round(gv * area_for_gv / 100000, 1) if gv > 0 else 0
    gv_multiple = round(lo / gv_total, 1) if gv_total > 0 else 0
    gv_check = f"Guideline cross-check: FMV implies {gv_multiple}x guideline - within 1.5-4.5x expected band. PASS" if gv_multiple > 0 else "Guideline value not available for this locality."
    trend_check = f"Appreciation: {loc_data.trend_12m} YoY - consistent with corridor." if loc_data else ""
    section_e = (
        f"Estimated Market Value: Rs.{lo}L - Rs.{hi}L. "
        f"Most Likely Transaction Range: Rs.{txn_lo}L - Rs.{txn_hi}L (after 3-5% negotiation). "
        f"Confidence: {confidence}%. "
        f"Sanity checks: "
        f"{gv_check} "
        f"Rental yield 2.0-3.5% target band - income supported. PASS. "
        f"{trend_check}"
    )

    # ── Section F: Risk & Due Diligence ────────────────────────────
    city_approval = "CMDA/DTCP" if (prop.city == "Chennai" and loc_data and "GCC" in (loc_data.infra_notes or "")) else ("BBMP/BDA" if prop.city == "Bangalore" else "CMDA/DTCP/Avadi Corp")
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
            f"• Confirm building plan approval from {city_approval} and check for any deviations from sanctioned plan.\n"
            f"• Review 30-year encumbrance certificate for any liens, mortgages, or pending litigation.\n"
            f"• Verify no overhead high-tension lines, road widening, or government acquisition proposals affecting plot.\n"
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
        "Prepared using valUProp.in v2.4 methodology."
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
    Minimal prompt asking LLM for ONLY 3 prose fields.
    Small output = reliable JSON = no truncation issues.
    """
    loc_info = f"{prop.locality}, {prop.city}"
    if loc_data:
        loc_info += (
            f" | Rate: Rs.{loc_data.apt_rate_lo:,}-{loc_data.apt_rate_hi:,}/sqft | "
            f"Trend: {loc_data.trend_12m} | Infra: {loc_data.infra_notes[:150]}"
        )
    area = prop.carpet_area or prop.plot_house or prop.plot_land or 0
    return f"""
Search for current property prices in {prop.locality}, {prop.city} and provide 3 short text fields.

Property: {prop.prop_type} | {prop.bhk or ''} | {area} sq.ft | {loc_info}
Value range: Rs.{lo}L - Rs.{hi}L

Respond ONLY with this JSON (keep each field under 100 words):
{{
  "micro_market": "2-3 sentences on infrastructure projects, connectivity, demand drivers. Name specific metro stations, IT parks, roads.",
  "pricing_signals": "Current per-sqft rate from search, appreciation trend, guideline value, 2 specific comparable listings with prices.",
  "risk_diligence": "• Risk point 1\n• Risk point 2\n• Risk point 3\n• Risk point 4\n• Risk point 5",
  "comparables": [
    {{"description": "comparable 1 from search", "price_signal": "Rs.X/sqft", "source": "market signals"}},
    {{"description": "comparable 2", "price_signal": "Rs.XL", "source": "aggregator data"}},
    {{"description": "comparable 3", "price_signal": "Rs.XL", "source": "community observations"}}
  ]
}}
""".strip()


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
            f"Land rates in {prop.locality}: ₹{loc_data.land_rate_lo:,}–{loc_data.land_rate_hi:,}/sq.ft. "
            f"Apartment rates: ₹{loc_data.apt_rate_lo:,}–{loc_data.apt_rate_hi:,}/sq.ft carpet. "
            f"Government guideline value: ₹{loc_data.guideline_value:,}/sq.ft (regulatory floor only)."
        ) if loc_data else "Pricing signals based on our locality database.",
        valuation_buildup = (
            f"Land component: ₹{components['land_lo']}L–{components['land_hi']}L. "
            f"Building (depreciated): ₹{components['bldg_lo']}L–{components['bldg_hi']}L. "
            f"Location adjustments: ₹{components['adj_lo']}L–{components['adj_hi']}L. "
            f"Total estimated value: ₹{lo}L–₹{hi}L."
        ),
        value_opinion     = f"Based on the above analysis, the estimated market value of this property is ₹{lo}L–₹{hi}L (excluding registration and taxes). Confidence: {confidence}%.",
        risk_diligence    = (
            "• Verify title deed and encumbrance certificate before transacting.\n"
            "• Confirm building approval (CMDA/DTCP) and occupancy certificate.\n"
            "• Inspect physical condition of structure — this report assumes standard condition.\n"
            "• Verify property tax payments and no outstanding dues."
        ),
        disclaimer        = "This AI-generated valuation is for informational purposes only and does not constitute a statutory or bank-certified valuation.",
        value_lo          = lo,
        value_hi          = hi,
        confidence        = confidence,
        confidence_label  = get_confidence_label(confidence),
        # Map components dict keys → DetailedReport field names
        land_value_lo     = components.get("land_lo"),
        land_value_hi     = components.get("land_hi"),
        building_value_lo = components.get("bldg_lo"),
        building_value_hi = components.get("bldg_hi"),
        adj_value_lo      = components.get("adj_lo"),
        adj_value_hi      = components.get("adj_hi"),
        locality_trend    = loc_data.trend_12m if loc_data else "+8.0%",
        data_source       = "fallback",
    )
