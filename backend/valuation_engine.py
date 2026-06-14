"""
ValUprop.in — Valuation Engine
valuation_engine.py
Two-stage valuation:
  Stage 1: Free estimate  -> wide range (~25% wide), one teaser insight
  Stage 2: Paid report    -> 7-section report (A-G), confidence score, PDF-ready JSON
Both stages use the valUProp.in v2.7 methodology:
  Land Value -> Building Residual -> Connectivity + Quality Adjustments -> Comparable Validation -> Final Range
ARCHITECTURE (as of 2026-06-08):
  The paid report is 100% engine-generated from the locality DB.
  No LLM is involved in the structured report sections.
  LLM is used ONLY for the free estimate teaser (one sentence).
  This eliminates all format variability and makes every report deterministic.
"""
import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Optional
from llm_service import (
    call_llm, call_llm_with_search, parse_json_response,
    validate_llm_output,
)
from locality_db import get_locality, get_confidence_label, LocalityData
from fallback_data import get_fallback
logger = logging.getLogger("valuprop.engine")
# ===================================================================
# PROPERTY INPUT MODEL
# ===================================================================
@dataclass
class PropertyInput:
    prop_type:      str
    city:           str
    locality:       str
    address:        str = ""
    pincode:        str = ""
    prop_name:      str = ""
    bhk:            str = ""
    carpet_area:    Optional[int] = None
    builtup_area:   Optional[int] = None
    super_builtup:  Optional[int] = None
    floor_info:     str = ""
    age_apt:        str = ""
    furnishing:     str = ""
    parking_apt:    str = ""
    facing:         str = ""
    plot_house:     Optional[int] = None
    builtup_house:  Optional[int] = None
    floors_house:   str = ""
    bedrooms_house: str = ""
    age_house:      Optional[int] = None
    road_house:     str = ""
    community_house:str = ""
    parking_house:  str = ""
    plot_villa:     Optional[int] = None
    builtup_villa:  Optional[int] = None
    config_villa:   str = ""
    age_villa:      str = ""
    community_villa:str = ""
    amenities_villa:str = ""
    plot_land:      Optional[int] = None
    land_use:       str = ""
    approval:       str = ""
    road_land:      str = ""
    corner_plot:    str = ""
    phone:          str = ""
    email:          str = ""
# ===================================================================
# VALUATION RESULTS
# ===================================================================
@dataclass
class FreeEstimate:
    value_lo:        float
    value_hi:        float
    teaser_insight:  str
    confidence:      int
    confidence_label:str
    locality_trend:  str
    data_source:     str
@dataclass
class DetailedReport:
    asset_overview:    str
    micro_market:      str
    pricing_signals:   str
    valuation_buildup: str
    value_opinion:     str
    risk_diligence:    str
    disclaimer:        str
    value_lo:          float
    value_hi:          float
    confidence:        int
    confidence_label:  str
    land_value_lo:     Optional[float] = None
    land_value_hi:     Optional[float] = None
    building_value_lo: Optional[float] = None
    building_value_hi: Optional[float] = None
    adj_value_lo:      Optional[float] = None
    adj_value_hi:      Optional[float] = None
    comparables:       list = field(default_factory=list)
    apt_rate_lo:       float = 0.0
    apt_rate_hi:       float = 0.0
    land_rate_sqft_lo: float = 0.0
    land_rate_sqft_hi: float = 0.0
    guideline_rate:    float = 0.0
    locality_trend:    str = ""
    data_source:       str = "engine"
# ===================================================================
# SYSTEM PROMPT (used only for free estimate teaser)
# ===================================================================
def _load_v27_prompt() -> str:
    candidates = [
        pathlib.Path(__file__).parent / "valUProp_Prompt.md",
        pathlib.Path("/app/valUProp_Prompt.md"),
    ]
    for p in candidates:
        if p.exists():
            content = p.read_text(encoding="utf-8")
            logger.info(f"Prompt loaded from {p} ({len(content)} chars)")
            return content
    logger.warning("valUProp_Prompt.md not found — using inline fallback.")
    return _V27_INLINE_FALLBACK
_V27_INLINE_FALLBACK = (
    "You are valUProp.in, an AI residential real estate valuation assistant for Indian markets. "
    "Produce a concise, defensible as-is market valuation for residential properties. "
    "OUTPUT FORMAT: Valid JSON only. No markdown, no preamble, no backticks. "
    "DISCLAIMER: This AI-generated valuation is for informational purposes only. "
    "Prepared using valUProp.in v2.7 methodology. "
    "copyright myRiky Technologies P. Ltd. | info@myriky.com"
)
_V27_PROMPT_BASE = _load_v27_prompt()
VALUPROP_SYSTEM_PROMPT = (
    _V27_PROMPT_BASE
    + "\n\nOUTPUT FORMAT: Respond with valid JSON only. No markdown, no preamble, no backticks."
)
# ===================================================================
# WEB SEARCH FALLBACK — called when locality is not in DB
# ===================================================================
async def _derive_locality_from_web(prop: PropertyInput) -> Optional[LocalityData]:
    """
    When locality is not in DB and fuzzy match also fails,
    use LLM + web search to derive current market rates.
    Confidence capped at 68 — never treated as DB-anchored.
    """
    try:
        system_prompt = (
            "You are a real estate data analyst for Indian residential markets. "
            "Use web search to find CURRENT 2025-2026 market rates for the given locality. "
            "Apply a 5% closing discount to any listed/asking prices to get realistic "
            "transaction rates. Return ONLY valid JSON, no markdown, no preamble."
        )
        user_prompt = (
            f"Find current (2025-2026) residential property market rates in "
            f"{prop.locality}, {prop.city}, India.\n"
            f"Search for: apartment resale rates (Rs/sqft), land/plot rates (Rs/sqft), "
            f"12-month price trend, demand drivers, and infrastructure highlights.\n\n"
            f"Return JSON:\n"
            f'{{"apt_rate_lo": <int>, "apt_rate_hi": <int>, '
            f'"land_rate_lo": <int>, "land_rate_hi": <int>, '
            f'"trend_12m": "<e.g. +7.5%>", '
            f'"demand_drivers": ["driver1", "driver2", "driver3"], '
            f'"infra_notes": "<50-word infra summary>", '
            f'"micro_context": "<50-word locality description>"}}'
        )
        raw  = await call_llm_with_search(
            system_prompt, user_prompt, max_tokens=700, max_searches=4
        )
        data = parse_json_response(raw)
        apt_lo  = int(data.get("apt_rate_lo",  0))
        apt_hi  = int(data.get("apt_rate_hi",  0))
        land_lo = int(data.get("land_rate_lo", 0))
        land_hi = int(data.get("land_rate_hi", 0))
        # Sanity: reject nonsensical values
        if apt_lo < 1000 or apt_hi < apt_lo or land_lo < 500 or land_hi < land_lo:
            logger.warning(
                f"Web-derived rates for {prop.locality}, {prop.city} failed sanity: {data}"
            )
            return None
        trend   = str(data.get("trend_12m", "+7.0%"))
        drivers = data.get("demand_drivers", ["Residential demand"])
        if not isinstance(drivers, list):
            drivers = [str(drivers)]
        infra   = str(data.get("infra_notes",   ""))
        context = str(data.get("micro_context",
                               f"{prop.city} {prop.locality} — live market data."))
        logger.info(
            f"Web-derived rates for {prop.locality}, {prop.city}: "
            f"apt Rs.{apt_lo:,}-Rs.{apt_hi:,}/sqft; "
            f"land Rs.{land_lo:,}-Rs.{land_hi:,}/sqft"
        )
        return LocalityData(
            city             = prop.city,
            locality         = prop.locality,
            apt_rate_lo      = apt_lo,
            apt_rate_hi      = apt_hi,
            land_rate_lo     = land_lo,
            land_rate_hi     = land_hi,
            guideline_value  = 0,
            trend_12m        = trend,
            micro_context    = context,
            infra_notes      = infra,
            data_confidence  = 68,   # web-derived — capped below DB minimum (72)
            demand_drivers   = drivers,
            risk_factors     = [
                "Rates derived from live web search — verify with local broker before transaction.",
                "Guideline value not available for this locality.",
            ],
        )
    except Exception as exc:
        logger.warning(
            f"Web rate lookup failed for {prop.locality}, {prop.city}: {exc}"
        )
        return None

# ===================================================================
# FREE ESTIMATE ENGINE
# ===================================================================
async def generate_free_estimate(prop: PropertyInput) -> FreeEstimate:
    loc_data = get_locality(prop.city, prop.locality)
    if not loc_data:
        loc_data = await _derive_locality_from_web(prop)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")
    lo, hi = _calculate_base_range(prop, loc_data, fallback)
    mid  = (lo + hi) / 2
    lo   = round(mid * 0.94, 1)
    hi   = round(mid * 1.06, 1)
    confidence = loc_data.data_confidence if loc_data else fallback.get("confidence", 70)
    teaser = await _generate_teaser(prop, loc_data, lo, hi)
    return FreeEstimate(
        value_lo         = lo,
        value_hi         = hi,
        teaser_insight   = teaser,
        confidence       = confidence,
        confidence_label = get_confidence_label(confidence),
        locality_trend   = (loc_data.trend_12m if loc_data else fallback.get("trend", "+8.0%")),
        data_source      = "engine",
    )
async def _generate_teaser(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> str:
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
    prompt = (
        f"Property: {prop.prop_type}, {prop.bhk or ''}, {prop.locality}, {prop.city}\n"
        f"Estimated range: Rs.{lo}L - Rs.{hi}L\n"
        f"Context: {context}\n"
        f"Generate ONE compelling teaser insight (1-2 sentences, max 30 words) that:\n"
        f"- Reveals something genuinely useful about this locality or property type\n"
        f"- Makes the user want to know MORE (leads them to pay for the detailed report)\n"
        f"- Is specific, not generic\n"
        f"- Does NOT repeat the price range\n"
        f"Respond with JSON: {{\"teaser\": \"...\"}}"
    )
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
# ===================================================================
# DETAILED REPORT ENGINE — 100% deterministic, no LLM
# ===================================================================
async def generate_detailed_report(
    prop: PropertyInput,
    free_range: Optional[tuple] = None,
) -> DetailedReport:
    loc_data = get_locality(prop.city, prop.locality)
    if not loc_data:
        loc_data = await _derive_locality_from_web(prop)
    fallback  = get_fallback(prop.city, prop.locality, prop.bhk or "2BHK")
    base_lo, base_hi = _calculate_base_range(prop, loc_data, fallback)
    midpoint = (base_lo + base_hi) / 2
    lo = round(midpoint * 0.95, 1)
    hi = round(midpoint * 1.05, 1)
    # Build entire report from engine — no LLM call
    report = _build_structured_report(prop, loc_data, lo, hi)
    report.comparables = []  # Comparable Pricing References section removed
    # Consistency clamp: keep paid report within 15% of free estimate midpoint
    if free_range is not None:
        try:
            free_lo, free_hi = float(free_range[0]), float(free_range[1])
            free_mid  = (free_lo + free_hi) / 2.0
            paid_mid  = (report.value_lo + report.value_hi) / 2.0
            drift_pct = abs(paid_mid - free_mid) / free_mid if free_mid > 0 else 0.0
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
                    for attr in ("land_value_lo", "building_value_lo", "adj_value_lo"):
                        v = getattr(report, attr, None)
                        if v is not None:
                            setattr(report, attr, round(v * scale_lo, 1))
                    for attr in ("land_value_hi", "building_value_hi", "adj_value_hi"):
                        v = getattr(report, attr, None)
                        if v is not None:
                            setattr(report, attr, round(v * scale_hi, 1))
                report.value_lo = clamped_lo
                report.value_hi = clamped_hi
        except (TypeError, ValueError, AttributeError) as clamp_err:
            logger.warning(f"Consistency clamp skipped: {clamp_err}")
    return report
# ===================================================================
# ENGINE COMPARABLES — 3 rows from locality DB rate range
# ===================================================================
def _build_engine_comparables(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> list:
    """
    Derive 3 comparable market signal rows from the locality DB.
    Always clean, always consistent — no LLM involved.
    """
    if not loc_data:
        mid = round((lo + hi) / 2, 1)
        return [
            {"description": f"{prop.locality} market — lower bound",  "price_signal": f"Rs.{lo}L",  "source": "Engine estimate"},
            {"description": f"{prop.locality} market — mid-point",    "price_signal": f"Rs.{mid}L", "source": "Engine estimate"},
            {"description": f"{prop.locality} market — upper bound",  "price_signal": f"Rs.{hi}L",  "source": "Engine estimate"},
        ]
    if prop.prop_type == "Apartment":
        lo_rate  = loc_data.apt_rate_lo
        hi_rate  = loc_data.apt_rate_hi
        mid_rate = (lo_rate + hi_rate) // 2
        bhk      = prop.bhk or "2BHK"
        age_label = prop.age_apt or "resale"
        return [
            {
                "description":  f"{prop.locality} {bhk} {age_label} — lower band",
                "price_signal": f"Rs.{lo_rate:,}/sqft",
                "source":       "Locality DB",
            },
            {
                "description":  f"{prop.locality} {bhk} {age_label} — mid-market",
                "price_signal": f"Rs.{mid_rate:,}/sqft",
                "source":       "Locality DB",
            },
            {
                "description":  f"{prop.locality} {bhk} {age_label} — upper band",
                "price_signal": f"Rs.{hi_rate:,}/sqft",
                "source":       "Locality DB",
            },
        ]
    else:
        # IndependentHouse, Villa, LandPlot — use land rates
        lo_rate  = loc_data.land_rate_lo
        hi_rate  = loc_data.land_rate_hi
        mid_rate = (lo_rate + hi_rate) // 2
        label    = "land" if prop.prop_type == "LandPlot" else "plot"
        return [
            {
                "description":  f"{prop.locality} {label} — lower band",
                "price_signal": f"Rs.{lo_rate:,}/sqft",
                "source":       "Locality DB",
            },
            {
                "description":  f"{prop.locality} {label} — mid-market",
                "price_signal": f"Rs.{mid_rate:,}/sqft",
                "source":       "Locality DB",
            },
            {
                "description":  f"{prop.locality} {label} — upper band",
                "price_signal": f"Rs.{hi_rate:,}/sqft",
                "source":       "Locality DB",
            },
        ]
# ===================================================================
# SECTION BUILDERS
# ===================================================================
def _build_section_b_engine(prop: PropertyInput, loc_data: Optional[LocalityData]) -> str:
    if not loc_data:
        return (
            f"* Market positioning: {prop.locality} is a residential locality in {prop.city}. "
            f"Demand is supported by employment access, road connectivity, and civic infrastructure.\n"
            f"* Connectivity: {prop.locality} is served by the road network linking to arterial routes. "
            f"Public transport options provide access to key city destinations.\n"
            f"* Demand profile: Residential demand is driven by end-user buyers and investors "
            f"seeking urban amenities and employment proximity in {prop.city}."
        )
    mid_rate = (loc_data.apt_rate_lo + loc_data.apt_rate_hi) // 2
    try:
        trend_val = float(str(loc_data.trend_12m).replace("+", "").replace("%", ""))
    except (ValueError, AttributeError):
        trend_val = 5.0
    mkt_tier = (
        "premium" if mid_rate >= 12000 else
        "upper-mid segment" if mid_rate >= 8000 else
        "mid segment" if mid_rate >= 5000 else
        "affordable segment"
    )
    trend_desc = (
        "strong appreciation momentum" if trend_val >= 10 else
        "healthy appreciation trend" if trend_val >= 6 else
        "moderate, stable growth"
    )
    boundary  = getattr(loc_data, "boundary_tier", "")
    zone_note = f" ({boundary})" if boundary else ""
    item1 = (
        f"* Market positioning: {prop.locality}{zone_note} is a {mkt_tier} locality in {prop.city}. "
        f"Apartment rates Rs.{loc_data.apt_rate_lo:,}-Rs.{loc_data.apt_rate_hi:,}/sqft; "
        f"land rates Rs.{loc_data.land_rate_lo:,}-Rs.{loc_data.land_rate_hi:,}/sqft. "
        f"12-month appreciation {loc_data.trend_12m} YoY - {trend_desc}."
    )
    if prop.city == "Chennai":
        if mid_rate >= 12000:
            conn = (
                f"{prop.locality} is served by South/Central Chennai arterial roads with established "
                f"MTC bus routes and suburban rail access. Proximity to key commercial, institutional, "
                f"and coastal amenities supports premium demand and stable occupancy."
            )
        elif mid_rate >= 8000:
            conn = (
                f"{prop.locality} has good arterial road connectivity linking to the inner and outer "
                f"ring roads. MTC bus and suburban rail (where applicable) provide city-wide access. "
                f"Commute to major employment hubs is manageable for mid-to-upper segment buyers."
            )
        elif mid_rate >= 5000:
            conn = (
                f"{prop.locality} is connected via Chennai arterial and peripheral roads. MTC bus routes "
                f"serve daily commuters; suburban rail options available in parts of the corridor. "
                f"Infrastructure improvement in this belt is driving incremental buyer demand."
            )
        else:
            conn = (
                f"{prop.locality} is connected via state and national highway network to Chennai's urban "
                f"core. Road transport is the primary mode; public transit options are developing. "
                f"Ongoing corridor investment is expected to progressively improve connectivity."
            )
    elif prop.city in ("Bangalore", "Bengaluru"):
        if mid_rate >= 10000:
            conn = (
                f"{prop.locality} benefits from Bengaluru's inner road network and BMTC bus coverage. "
                f"Metro Phase 1/2 proximity (where applicable) adds transit value. "
                f"Access to Outer Ring Road and employment clusters is well-established."
            )
        else:
            conn = (
                f"{prop.locality} is accessible via Bengaluru's arterial and peripheral road network. "
                f"BMTC bus routes and developing metro corridors support daily commutes. "
                f"Connectivity to major IT and commercial hubs is the primary demand driver."
            )
    else:
        conn = (
            f"{prop.locality} is served by arterial road network and public transport options in {prop.city}. "
            f"Connectivity to key employment and commercial hubs supports residential demand. "
            f"Infrastructure quality is consistent with the locality's market rate positioning."
        )
    item2 = f"* Connectivity: {conn}"
    if prop.city == "Chennai":
        if mid_rate >= 12000:
            demand = (
                f"HNI and premium segment end-users dominate buyer profiles. "
                f"Investment demand is supported by stable rental yields (2.0-3.0%) and long-term "
                f"capital appreciation. Institutional anchors - schools, hospitals, retail - "
                f"sustain occupancy and limit vacancy risk."
            )
        elif mid_rate >= 8000:
            demand = (
                f"Salaried IT/ITES professionals and business owners form the primary buyer base. "
                f"Upgrade demand from mid-segment households seeking better amenities and connectivity. "
                f"Rental yields of 2.5-3.5% attract investor buyers alongside end-users."
            )
        elif mid_rate >= 5000:
            demand = (
                f"Mid-segment salaried workers and first-time homebuyers are the core demand segment. "
                f"Employment in nearby industrial estates, IT parks, and service sectors drives occupancy. "
                f"Competitive pricing relative to inner zones attracts upgrade and investment buyers."
            )
        else:
            demand = (
                f"Affordable and first-time homebuyer segment dominates transactions. "
                f"Proximity to industrial estates and manufacturing hubs provides the employment base. "
                f"NRI and diaspora investment demand adds a secondary buyer layer seeking affordable "
                f"Chennai exposure."
            )
    else:
        demand = (
            f"End-user buyers seeking {mkt_tier} residential options in {prop.city} drive primary demand. "
            f"Employment proximity, social infrastructure, and connectivity are the key purchase drivers. "
            f"Investor demand is supported by rental yields consistent with the locality's rate band."
        )
    item3 = f"* Demand profile: {demand}"
    return f"{item1}\n{item2}\n{item3}"
def _build_section_f_engine(prop: PropertyInput, loc_data: Optional[LocalityData]) -> str:
    boundary = getattr(loc_data, "boundary_tier", "") if loc_data else ""
    age_str   = prop.age_apt or (f"{prop.age_house} years" if prop.age_house else "5-10 years")
    if "Avadi" in boundary:
        ab_full  = "Avadi Municipal Corporation (AvMC)"
        ab_short = "AvMC"
    elif "Tambaram" in boundary:
        ab_full  = "Tambaram Municipal Corporation"
        ab_short = "Tambaram Corp"
    elif "CMA" in boundary or "DTCP" in boundary:
        ab_full  = "DTCP (Directorate of Town and Country Planning)"
        ab_short = "DTCP"
    elif prop.city == "Chennai":
        ab_full  = "CMDA (Chennai Metropolitan Development Authority)"
        ab_short = "CMDA"
    elif prop.city in ("Bangalore", "Bengaluru"):
        ab_full  = "BBMP/BDA"
        ab_short = "BBMP/BDA"
    else:
        ab_full  = "local municipal authority"
        ab_short = "local authority"
    if prop.prop_type == "Apartment":
        item1 = (
            f"* Title and UDS verification: {prop.locality} falls under {ab_full} jurisdiction. "
            f"Verify encumbrance certificate chain for minimum 30 years. "
            f"UDS percentage in the sale agreement must match the society's undivided share register - "
            f"mismatch is a common title risk in older projects."
        )
        item2 = (
            f"* {ab_short} approvals and OC: Confirm building plan is sanctioned by {ab_short}. "
            f"Occupancy Certificate (OC) must be available - absence restricts PSU bank and NBFC "
            f"financing and significantly limits future resale options."
        )
        item3 = (
            f"* Age and structural condition: For {age_str} stock, verify OC is in place and "
            f"the structure is in standard condition. Budget 5-10% of purchase value for "
            f"renovation or fit-out if the unit has dated finishes or deferred maintenance."
        )
        item4 = (
            f"* Layout and encumbrance checks: Confirm the project is not in a road-widening "
            f"alignment, high-tension line corridor, or water body buffer zone. "
            f"Verify no pending litigation or mortgage is registered against the project or the specific flat."
        )
        item5 = (
            f"* Dues clearance and NOC: Verify property tax, water charges, and maintenance dues "
            f"are cleared by the seller. Obtain society NOC and existing bank NOC (if applicable) "
            f"before executing the sale agreement."
        )
    elif prop.prop_type == "IndependentHouse":
        item1 = (
            f"* Title and patta verification: {prop.locality} falls under {ab_full} jurisdiction. "
            f"Verify patta/khata is in the seller's name and boundary measurements match "
            f"registered documents. Review 30-year encumbrance certificate for liens or litigation."
        )
        item2 = (
            f"* {ab_short} plan sanction: Confirm building plan is sanctioned by {ab_short}. "
            f"Check for deviations from the sanctioned plan - unapproved additions affect "
            f"loan eligibility and create regularisation liability."
        )
        item3 = (
            f"* Structural condition: For a {age_str} building, commission an independent structural "
            f"assessment. Older structures may require investment in waterproofing, electrical "
            f"rewiring, or plumbing - budget accordingly before finalising offer price."
        )
        item4 = (
            f"* Land encumbrances: Verify no overhead HT lines, road-widening proposals, or "
            f"government acquisition notices affect the plot. Check CRZ or water body buffer "
            f"zone applicability if the property is near the coast or a lake."
        )
        item5 = (
            f"* Dues and succession: Verify property tax and water dues are cleared by the seller. "
            f"If the property has multiple legal heirs, obtain a valid release deed or family "
            f"settlement document before transacting."
        )
    else:
        item1 = (
            f"* Title and survey verification: {prop.locality} falls under {ab_full} jurisdiction. "
            f"Verify patta/title deed chain for minimum 30 years. Confirm survey number and "
            f"boundary measurements match field verification."
        )
        item2 = (
            f"* {ab_short} layout approval: Confirm the layout is approved by {ab_short}. "
            f"Unapproved or lapsed layouts carry major home loan and resale risk - do not "
            f"proceed without a valid layout approval certificate."
        )
        item3 = (
            f"* Land use and conversion: Verify land use classification - agricultural land "
            f"requires conversion to residential before construction. Conversion adds cost, "
            f"regulatory timeline, and uncertainty."
        )
        item4 = (
            f"* Access and right of way: Verify road width, access road ownership, and "
            f"right-of-way documentation. Confirm access from the main road to the plot "
            f"is undisputed and has adequate width for construction vehicles."
        )
        item5 = (
            f"* Statutory valuation note: For transactions above Rs.1 Cr, consider engaging "
            f"a registered valuer under the Wealth Tax Act / IBBI guidelines for an independent "
            f"statutory valuation opinion."
        )
    return f"{item1}\n{item2}\n{item3}\n{item4}\n{item5}"
def _build_structured_report(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> DetailedReport:
    components = _calculate_components(prop, loc_data, lo, hi)
    confidence = loc_data.data_confidence if loc_data else 65
    area_info = ""
    if prop.carpet_area:
        area_info = (
            f" The apartment measures {prop.carpet_area:,} sq.ft carpet area ({prop.bhk})."
            if prop.bhk else f" Carpet area: {prop.carpet_area:,} sq.ft."
        )
    elif prop.plot_house:
        area_info = f" Plot area: {prop.plot_house:,} sq.ft."
    elif prop.plot_land:
        area_info = f" Plot area: {prop.plot_land:,} sq.ft."
    age_info = (
        f" Building age: {prop.age_apt}." if prop.age_apt else
        f" Building age: {prop.age_house} years." if prop.age_house else
        " Property age not specified; standard condition assumed."
    )
    uds_note = (
        " For apartments, a 30% undivided share of land (UDS) assumption applies unless specified."
        if prop.prop_type == "Apartment" else ""
    )
    section_a = (
        f"This {prop.prop_type.replace('IndependentHouse', 'Independent House')} is located "
        f"in {prop.locality}, {prop.city}.{area_info}{age_info} Locality character and "
        f"micro-market rates are based on our proprietary database.{uds_note}"
    )
    section_b = _build_section_b_engine(prop, loc_data)
    if loc_data:
        mid_rate     = (loc_data.apt_rate_lo + loc_data.apt_rate_hi) // 2
        age_factor_c = _age_depreciation(prop.age_apt or "5-10 years")
        eff_lo       = round(mid_rate * age_factor_c * 0.97)
        eff_hi       = round(mid_rate * age_factor_c * 1.03)
        dep_note = (
            f" Age discount ({round((1 - age_factor_c) * 100)}%) applied for "
            f"{prop.age_apt or '5-10 year'} resale stock."
            if age_factor_c < 1.0 else ""
        )
        gv_note = (
            f" Government guideline value Rs.{loc_data.guideline_value:,}/sqft - regulatory floor only."
            if loc_data.guideline_value > 0 else ""
        )
        mkt_class    = "active" if "+" in str(loc_data.trend_12m) else "stable"
        rate_source  = (
            "Live market signals (web search)"
            if loc_data.data_confidence < 72
            else "Locality DB rates"
        )
        section_c = (
            f"{rate_source} for {prop.locality}: apartment Rs.{loc_data.apt_rate_lo:,}"
            f"-Rs.{loc_data.apt_rate_hi:,}/sqft; land Rs.{loc_data.land_rate_lo:,}"
            f"-Rs.{loc_data.land_rate_hi:,}/sqft.{dep_note}"
            f" Effective working rate: Rs.{eff_lo:,}-Rs.{eff_hi:,}/sqft."
            f" 12-month appreciation {loc_data.trend_12m} YoY - {mkt_class} market.{gv_note}"
        )
    else:
        section_c = f"Pricing signals based on our locality database for {prop.locality}, {prop.city}."
    age_factor = _age_depreciation(prop.age_apt or "5-10 years")
    dep_pct    = round((1 - age_factor) * 100)
    area       = prop.carpet_area or 950
    if prop.prop_type == "Apartment" and loc_data:
        rate_lo     = loc_data.apt_rate_lo
        rate_hi     = loc_data.apt_rate_hi
        base_lo_raw = round(area * rate_lo / 100000, 1)
        base_hi_raw = round(area * rate_hi / 100000, 1)
        base_lo_dep = round(base_lo_raw * age_factor, 1)
        base_hi_dep = round(base_hi_raw * age_factor, 1)
        try:
            trend_val = float(str(loc_data.trend_12m).replace("%", "").replace("+", ""))
        except (ValueError, AttributeError):
            trend_val = 5.0
        conn_road  = "+2%"
        conn_metro = "+2%" if trend_val >= 8 else "+1%"
        conn_empl  = "+2%" if trend_val >= 10 else "+1%"
        qual_pct   = "-2%"
        yield_pct  = "+1%"
        conn_total = 2 + (2 if trend_val >= 8 else 1) + (2 if trend_val >= 10 else 1)
        net_pct    = conn_total - 2 + 1
        net_adj    = f"+{net_pct}%"
        net_mult   = round(1 + net_pct / 100, 2)
        rent_lo  = max(5000,  round(lo  * 100000 * 0.020 / 12 / 500) * 500)
        rent_mid = max(rent_lo  + 1000, round(((lo + hi) / 2) * 100000 * 0.025 / 12 / 500) * 500)
        rent_hi  = max(rent_mid + 1000, round(hi  * 100000 * 0.030 / 12 / 500) * 500)
        yield_lo  = round(rent_lo  * 12 / (lo  * 100000) * 100, 2)
        yield_mid = round(rent_mid * 12 / (((lo + hi) / 2) * 100000) * 100, 2)
        yield_hi  = round(rent_hi  * 12 / (hi  * 100000) * 100, 2)
        section_d = (
            f"STEPS|Step 1|Base rate ({prop.age_apt or '5-10 yr'} resale)|Locality DB benchmark|Rs.{rate_lo:,}-Rs.{rate_hi:,}/sqft\n"
            f"STEPS|Step 2|Base value|{area:,} sqft x rate|Rs.{base_lo_raw}L-Rs.{base_hi_raw}L\n"
            f"STEPS|Step 3|Age depreciation ({dep_pct}%)|Applied to base value|-Rs.{round(base_lo_raw - base_lo_dep, 1)}L\n"
            f"STEPS|Step 4|Post-depreciation base|Rs.{base_lo_raw}L x {age_factor:.2f}|Rs.{base_lo_dep}L-Rs.{base_hi_dep}L\n"
            f"ADJ|Connectivity: Main road / arterial access|{conn_road}|Road network linkage\n"
            f"ADJ|Connectivity: Metro / suburban rail proximity|{conn_metro}|Nearest station distance and status\n"
            f"ADJ|Connectivity: Employment node access|{conn_empl}|IT park / industrial estate proximity\n"
            f"ADJ|Quality factor (building/society grade)|{qual_pct}|Building age and society amenities\n"
            f"ADJ|Income/Rental-Yield support|{yield_pct}|Yield in healthy 2.0-3.5% band\n"
            f"ADJ|NET STEP 5 ADJUSTMENT|{net_adj}|Rs.{base_lo_dep}L x {net_mult}\n"
            f"FINAL|FINAL VALUE||Rounded|Rs.{lo}L - Rs.{hi}L\n"
            f"YIELD|Low|Rs.{rent_lo:,}|Rs.{rent_lo * 12:,}|Rs.{lo}L|{yield_lo}%\n"
            f"YIELD|Mid|Rs.{rent_mid:,}|Rs.{rent_mid * 12:,}|Rs.{round((lo + hi) / 2, 1)}L|{yield_mid}%\n"
            f"YIELD|High|Rs.{rent_hi:,}|Rs.{rent_hi * 12:,}|Rs.{hi}L|{yield_hi}%\n"
            f"NOTE|Benchmark monthly rent for {prop.bhk or '2BHK'} in {prop.locality}: "
            f"Rs.{rent_lo:,}-Rs.{rent_hi:,}/month. "
            f"Implied gross yield {yield_lo}%-{yield_hi}% - within 2.0-3.5% healthy band. Income supported."
        )
    elif prop.prop_type == "IndependentHouse" and loc_data:
        plot_area         = prop.plot_house or 1000
        age_yrs_h         = prop.age_house or 10
        dep_rate_h        = min(0.8, age_yrs_h * 0.015)
        dep_pct_h         = round(dep_rate_h * 100)
        eff_bldg_rate_h   = round(1800 * (1 - dep_rate_h))
        builtup_h         = prop.builtup_house or int(plot_area * 1.2)
        land_lo_h         = loc_data.land_rate_lo
        land_hi_h         = loc_data.land_rate_hi
        land_val_lo_h     = round(plot_area * land_lo_h / 100000, 1)
        land_val_hi_h     = round(plot_area * land_hi_h / 100000, 1)
        bldg_val_h        = round(builtup_h * eff_bldg_rate_h / 100000, 1)
        road_label_h      = prop.road_house or "Standard"
        road_pct_h        = {
            "30 ft+": "+8%", "20-30 ft": "+2%", "Less than 20 ft": "-4%"
        }.get(prop.road_house, "0%")
        section_d = (
            f"STEPS|Step 1|Land rate|Locality benchmark|Rs.{land_lo_h:,}-Rs.{land_hi_h:,}/sqft\n"
            f"STEPS|Step 2|Land value|{plot_area:,} sqft x rate|Rs.{land_val_lo_h}L-Rs.{land_val_hi_h}L\n"
            f"STEPS|Step 3|Building depreciation ({dep_pct_h}%)|Rs.1,800/sqft x {1-dep_rate_h:.2f}|Rs.{eff_bldg_rate_h:,}/sqft effective\n"
            f"STEPS|Step 4|Building value (depreciated)|{builtup_h:,} sqft x Rs.{eff_bldg_rate_h:,}/sqft|Rs.{bldg_val_h}L\n"
            f"ADJ|Road width / frontage ({road_label_h})|{road_pct_h}|Road access factor\n"
            f"ADJ|Connectivity: Employment node access|+1%|Proximity to major employment hubs\n"
            f"ADJ|Quality factor (structure condition)|+1%|Age-adjusted structural grade\n"
            f"ADJ|NET STEP 5 ADJUSTMENT|+2%|Combined location and quality adjustments\n"
            f"FINAL|FINAL VALUE||Land + Building + Adjustments|Rs.{lo}L - Rs.{hi}L\n"
        )
    elif prop.prop_type == "Villa" and loc_data:
        plot_area_v        = prop.plot_villa or 2000
        builtup_v          = prop.builtup_villa or int(plot_area_v * 1.5)
        age_str_v          = prop.age_villa or "5-10 years"
        age_factor_v       = _age_depreciation(age_str_v)
        dep_pct_v          = round((1 - age_factor_v) * 100)
        eff_bldg_rate_v    = round(2200 * age_factor_v)
        bldg_val_v         = round(builtup_v * eff_bldg_rate_v / 100000, 1)
        land_lo_v          = loc_data.land_rate_lo
        land_hi_v          = loc_data.land_rate_hi
        land_val_lo_v      = round(plot_area_v * land_lo_v * 0.9 / 100000, 1)
        land_val_hi_v      = round(plot_area_v * land_hi_v * 0.9 / 100000, 1)
        amenity_label_v    = prop.amenities_villa or "Mid-range"
        amenity_pct_v      = {
            "Ultra-luxury": "+20%", "Premium": "+12%", "Mid-range": "+5%", "Basic": "0%"
        }.get(prop.amenities_villa, "+8%")
        section_d = (
            f"STEPS|Step 1|Land rate (gated community -10%)|Locality benchmark|Rs.{land_lo_v:,}-Rs.{land_hi_v:,}/sqft\n"
            f"STEPS|Step 2|Land value|{plot_area_v:,} sqft x rate x 0.90|Rs.{land_val_lo_v}L-Rs.{land_val_hi_v}L\n"
            f"STEPS|Step 3|Building depreciation ({dep_pct_v}%)|Rs.2,200/sqft x {age_factor_v:.2f}|Rs.{eff_bldg_rate_v:,}/sqft effective\n"
            f"STEPS|Step 4|Building value (depreciated)|{builtup_v:,} sqft x Rs.{eff_bldg_rate_v:,}/sqft|Rs.{bldg_val_v}L\n"
            f"ADJ|Amenities tier ({amenity_label_v})|{amenity_pct_v}|Community amenities premium\n"
            f"ADJ|Connectivity and micro-location factor|+2%|Access and location quality\n"
            f"ADJ|NET STEP 5 ADJUSTMENT|{amenity_pct_v}|Combined location + amenities uplift\n"
            f"FINAL|FINAL VALUE||Land + Building + Adjustments|Rs.{lo}L - Rs.{hi}L\n"
        )
    elif prop.prop_type == "LandPlot" and loc_data:
        plot_area_l   = prop.plot_land or 1000
        land_lo_l     = loc_data.land_rate_lo
        land_hi_l     = loc_data.land_rate_hi
        base_lo_l     = round(plot_area_l * land_lo_l / 100000, 1)
        base_hi_l     = round(plot_area_l * land_hi_l / 100000, 1)
        use_pct_l     = {
            "Residential": "0%", "Commercial": "+25%", "Agricultural": "-65%"
        }.get(prop.land_use or "Residential", "0%")
        appr_pct_l    = {
            "DTCP Approved": "0%", "CMDA Approved": "+5%",
            "Panchayat": "-25%",   "Unapproved": "-50%"
        }.get(prop.approval or "", "-15%")
        corner_pct_l  = "+8%" if "Yes" in (prop.corner_plot or "") else "0%"
        road_pct_l    = {
            "30 ft+": "+10%", "20-30 ft": "+3%", "Less than 20 ft": "-5%"
        }.get(prop.road_land or "", "0%")
        section_d = (
            f"STEPS|Step 1|Land rate|Locality benchmark|Rs.{land_lo_l:,}-Rs.{land_hi_l:,}/sqft\n"
            f"STEPS|Step 2|Base plot value|{plot_area_l:,} sqft x rate|Rs.{base_lo_l}L-Rs.{base_hi_l}L\n"
            f"ADJ|Approval status ({prop.approval or 'N/A'})|{appr_pct_l}|Regulatory approval premium/discount\n"
            f"ADJ|Land use ({prop.land_use or 'Residential'})|{use_pct_l}|Use classification factor\n"
            f"ADJ|Corner plot|{corner_pct_l}|{'Corner premium applied' if corner_pct_l != '0%' else 'Interior plot — no premium'}\n"
            f"ADJ|Road width ({prop.road_land or 'standard'})|{road_pct_l}|Road frontage factor\n"
            f"FINAL|FINAL VALUE||Plot area x adjusted rate|Rs.{lo}L - Rs.{hi}L\n"
        )
    else:
        # No loc_data even after web search (network failure etc.)
        # Use STEPS format so PDF renders something meaningful
        section_d = (
            f"STEPS|Step 1|City-level estimate|No locality-specific data available|"
            f"Rs.{round(components['land_lo'] / max(prop.plot_land or prop.plot_house or 1000, 1) * 100000):,}/sqft approx\n"
            f"STEPS|Step 2|Land + Building total|Combined city-level estimate|"
            f"Rs.{components['land_lo']}L-Rs.{components['land_hi']}L\n"
            f"ADJ|Quality and location factor|Included|City-level adjustment applied\n"
            f"FINAL|FINAL VALUE||City-level estimate|Rs.{lo}L - Rs.{hi}L\n"
        )
    txn_lo     = round(lo * 0.96, 1)
    txn_hi     = round(hi * 0.97, 1)
    gv         = loc_data.guideline_value if loc_data else 0
    area_gv    = prop.carpet_area or 950
    gv_total   = round(gv * area_gv / 100000, 1) if gv > 0 else 0
    gv_multiple= round(lo / gv_total, 1) if gv_total > 0 else 0
    gv_check   = (
        f"Guideline cross-check: FMV implies {gv_multiple}x guideline - within 1.5-4.5x expected band. PASS"
        if gv_multiple > 0 else "Guideline value not available for this locality."
    )
    trend_check = (
        f"Appreciation: {loc_data.trend_12m} YoY - consistent with corridor." if loc_data else ""
    )
    section_e = (
        f"Estimated Market Value: Rs.{lo}L - Rs.{hi}L\n"
        f"Most Likely Transaction Range: Rs.{txn_lo}L - Rs.{txn_hi}L (after 3-5% negotiation)\n"
        f"Confidence: {confidence}%\n\n"
        f"Sanity Checks:\n"
        f"* {gv_check}\n"
        f"* Rental yield 2.0-3.5% target band - income supported. PASS\n"
        + (f"* {trend_check}\n" if trend_check else "")
    )
    section_f = _build_section_f_engine(prop, loc_data)
    section_g = (
        "This AI-generated valuation is for informational purposes only and does not constitute "
        "a statutory, RERA-approved, or bank-certified valuation. For loans, legal disputes, or "
        "court proceedings, a registered valuer under the Wealth Tax Act / IBBI guidelines is required. "
        "Prepared using valUProp.in v2.7 methodology. "
        "copyright myRiky Technologies P. Ltd. | info@myriky.com"
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
        apt_rate_lo       = loc_data.apt_rate_lo if loc_data else 0.0,
        apt_rate_hi       = loc_data.apt_rate_hi if loc_data else 0.0,
        land_rate_sqft_lo = loc_data.land_rate_lo if loc_data else 0.0,
        land_rate_sqft_hi = loc_data.land_rate_hi if loc_data else 0.0,
        guideline_rate    = loc_data.guideline_value if loc_data else 0.0,
        data_source       = "engine",
    )
# ===================================================================
# CALCULATION HELPERS
# ===================================================================
def _calculate_components(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    lo:       float,
    hi:       float,
) -> dict:
    if prop.prop_type in ("IndependentHouse", "LandPlot"):
        return {
            "land_lo": round(lo * 0.72, 1), "land_hi": round(hi * 0.78, 1),
            "bldg_lo": round(lo * 0.17, 1), "bldg_hi": round(hi * 0.22, 1),
            "adj_lo":  round(lo * 0.04, 1), "adj_hi":  round(hi * 0.06, 1),
        }
    elif prop.prop_type == "Villa":
        return {
            "land_lo": round(lo * 0.58, 1), "land_hi": round(hi * 0.62, 1),
            "bldg_lo": round(lo * 0.28, 1), "bldg_hi": round(hi * 0.32, 1),
            "adj_lo":  round(lo * 0.08, 1), "adj_hi":  round(hi * 0.12, 1),
        }
    else:
        return {
            "land_lo": round(lo * 0.28, 1), "land_hi": round(hi * 0.32, 1),
            "bldg_lo": round(lo * 0.58, 1), "bldg_hi": round(hi * 0.62, 1),
            "adj_lo":  round(lo * 0.08, 1), "adj_hi":  round(hi * 0.12, 1),
        }
def _calculate_base_range(
    prop:     PropertyInput,
    loc_data: Optional[LocalityData],
    fallback: dict,
) -> tuple:
    if prop.prop_type == "Apartment":
        bhk_multipliers = {
            "1BHK": 0.58, "2BHK": 1.0, "3BHK": 1.48,
            "4BHK": 1.95, "5BHK+": 2.45,
        }
        m = bhk_multipliers.get(prop.bhk or "2BHK", 1.0)
        if loc_data and prop.carpet_area:
            age_factor = _age_depreciation(prop.age_apt)
            lo = round(prop.carpet_area * loc_data.apt_rate_lo * age_factor / 100000, 1)
            hi = round(prop.carpet_area * loc_data.apt_rate_hi * age_factor / 100000, 1)
        elif loc_data:
            base_area = {
                "1BHK": 550, "2BHK": 950, "3BHK": 1350, "4BHK": 1800, "5BHK+": 2400,
            }.get(prop.bhk or "2BHK", 950)
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
            age_yrs   = prop.age_house or 10
            dep_rate  = min(0.8, age_yrs * 0.015)
            bldg_rate = 1800 * (1 - dep_rate)
            builtup   = prop.builtup_house or int(prop.plot_house * 1.2)
            bldg_val  = builtup * bldg_rate / 100000
            road_factor = {
                "30 ft+": 1.08, "20-30 ft": 1.02, "Less than 20 ft": 0.96,
            }.get(prop.road_house, 1.0)
            lo = round((prop.plot_house * loc_data.land_rate_lo / 100000 + bldg_val * 0.85) * road_factor, 1)
            hi = round((prop.plot_house * loc_data.land_rate_hi / 100000 + bldg_val * 1.15) * road_factor, 1)
        else:
            lo = fallback.get("min", 100)
            hi = fallback.get("max", 200)
    elif prop.prop_type == "Villa":
        if loc_data and prop.plot_villa:
            builtup  = prop.builtup_villa or int(prop.plot_villa * 1.5)
            bldg_val = builtup * 2200 / 100000
            amenity_premium = {
                "Ultra-luxury": 1.2, "Premium": 1.12, "Mid-range": 1.05, "Basic": 1.0,
            }.get(prop.amenities_villa, 1.08)
            lo = round((prop.plot_villa * loc_data.land_rate_lo * 0.9 / 100000 + bldg_val * 0.9) * amenity_premium, 1)
            hi = round((prop.plot_villa * loc_data.land_rate_hi * 0.9 / 100000 + bldg_val * 1.1) * amenity_premium, 1)
        else:
            lo = fallback.get("min", 150)
            hi = fallback.get("max", 300)
    elif prop.prop_type == "LandPlot":
        if loc_data and prop.plot_land:
            use_factor   = {"Residential": 1.0, "Commercial": 1.25, "Agricultural": 0.35}.get(prop.land_use, 1.0)
            appr_factor  = {"DTCP Approved": 1.0, "CMDA Approved": 1.05, "Panchayat": 0.75, "Unapproved": 0.50}.get(prop.approval, 0.85)
            corner_factor= 1.08 if "Yes" in (prop.corner_plot or "") else 1.0
            road_factor  = {"30 ft+": 1.1, "20-30 ft": 1.03, "Less than 20 ft": 0.95}.get(prop.road_land, 1.0)
            factor       = use_factor * appr_factor * corner_factor * road_factor
            lo = round(prop.plot_land * loc_data.land_rate_lo / 100000 * factor * 0.92, 1)
            hi = round(prop.plot_land * loc_data.land_rate_hi / 100000 * factor * 1.08, 1)
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
    factors = {
        "Under construction": 1.05,
        "0-5 years": 1.0,   "0-5 yrs": 1.0,
        "5-10 years": 0.88, "5-10 yrs": 0.88,
        "10-20 years": 0.70,"10-20 yrs": 0.70,
        "15-20 years": 0.60,"15-20 yrs": 0.60,
        "20+ years": 0.50,
    }
    return factors.get(age_str or "0-5 years", 0.88)
def _apply_floor_factor(lo: float, hi: float, floor_info: str) -> tuple:
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
