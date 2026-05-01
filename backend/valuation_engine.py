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
"""

import json
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from llm_service import call_llm, parse_json_response
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

    # ── Widen range by 25% for free tier (incentivises paid upgrade)
    mid  = (lo + hi) / 2
    lo   = round(mid * 0.875, 1)
    hi   = round(mid * 1.125, 1)

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
        return data.get("teaser", _fallback_teaser(prop, loc_data))
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

async def generate_detailed_report(prop: PropertyInput) -> DetailedReport:
    """
    Generate the full 7-section ValUprop report using LLM.
    Sections A–G as per GPT Instructions v2.1.
    """
    loc_data = get_locality(prop.city, prop.locality)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")

    # ── Base price range (tighter for paid tier, ~10–15% wide)
    lo, hi = _calculate_base_range(prop, loc_data, fallback)

    # ── Build detailed prompt ─────────────────────────────────────
    user_prompt = _build_report_prompt(prop, loc_data, lo, hi)

    # ── Call LLM ─────────────────────────────────────────────────
    try:
        raw  = await call_llm(
            VALUPROP_SYSTEM_PROMPT,
            user_prompt,
            max_tokens  = 2000,
            temperature = 0.25,
            expect_json = True,
        )
        data = parse_json_response(raw)
        return _parse_report_response(data, prop, loc_data, lo, hi)
    except Exception as e:
        logger.error(f"Detailed report LLM failed: {e}")
        # Return a graceful fallback
        return _build_fallback_report(prop, loc_data, lo, hi)


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
        **{k: v for k, v in components.items() if k in [
            "land_lo", "land_hi", "bldg_lo", "bldg_hi", "adj_lo", "adj_hi"
        ]},
        locality_trend    = loc_data.trend_12m if loc_data else "+8.0%",
        data_source       = "fallback",
    )
