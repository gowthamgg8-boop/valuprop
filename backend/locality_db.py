"""
ValUprop.in — Locality Price Database
locality_db.py

This is our proprietary data layer — the competitive moat.
Every report request enriches this database.

Structure:
  - Baseline rates per locality (land ₹/sq.ft, apt ₹/sq.ft)
  - Guideline values (state-published, updated annually)
  - Micro-market context (LLM uses this for narrative)
  - 12-month trend
  - Confidence level (how good our data is for this area)

UPDATE SCHEDULE:
  - Guideline values: annually (state publishes)
  - Market rates: monthly (manual research + user submissions)
  - Trend data: quarterly

Last updated: May 2026 (realistic market rates)
"""

from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LocalityData:
    city:              str
    locality:          str
    # Land rates (₹/sq.ft)
    land_rate_lo:      float        # conservative
    land_rate_hi:      float        # optimistic
    # Apartment rates (₹/sq.ft carpet)
    apt_rate_lo:       float
    apt_rate_hi:       float
    # Guideline value (₹/sq.ft) — government published, always lower than market
    guideline_value:   float
    # 12-month appreciation trend
    trend_12m:         str          # e.g. "+8.2%"
    # Micro-market context — used in Section B of report
    micro_context:     str
    # Key infrastructure notes
    infra_notes:       str
    # Data confidence (0-100)
    data_confidence:   int          = 75
    # Demand drivers
    demand_drivers:    list         = field(default_factory=list)
    # Risk factors
    risk_factors:      list         = field(default_factory=list)

# ═══════════════════════════════════════════════════════════════════
# CHENNAI LOCALITIES
# ═══════════════════════════════════════════════════════════════════

LOCALITY_DB: dict[str, LocalityData] = {

    # ── Chennai ──────────────────────────────────────────────────

    "Chennai|Anna Nagar": LocalityData(
        city="Chennai", locality="Anna Nagar",
        land_rate_lo=28000, land_rate_hi=50000,
        apt_rate_lo=14000,   apt_rate_hi=22000,
        guideline_value=11000,
        trend_12m="+6.2%",
        micro_context=(
            "Anna Nagar is a well-established, mature residential locality in North-West Chennai. "
            "It is one of the most sought-after addresses in the city, known for its planned grid layout, "
            "wide roads, and proximity to the Western Express Highway. Demand is consistently high due to "
            "strong social infrastructure and excellent connectivity."
        ),
        infra_notes=(
            "Metro Rail (Green Line) stations at Anna Nagar East and Anna Nagar Tower. "
            "Proximity to Koyambedu CMBT (bus terminus). CMDA approved zone. "
            "Well-served by top schools (DAV, Santhome), hospitals (Apollo Spectra, MIOT), "
            "and commercial hubs (Spencer Plaza corridor)."
        ),
        data_confidence=88,
        demand_drivers=["Metro connectivity", "Mature social infrastructure", "Premium address", "CMDA approval"],
        risk_factors=["Older building stock in inner areas", "Parking constraints on narrow streets"],
    ),

    "Chennai|T. Nagar": LocalityData(
        city="Chennai", locality="T. Nagar",
        land_rate_lo=35000, land_rate_hi=60000,
        apt_rate_lo=16000,   apt_rate_hi=24000,
        guideline_value=13000,
        trend_12m="+7.5%",
        micro_context=(
            "T. Nagar (Thyagaraya Nagar) is Chennai's premier commercial and residential hub, "
            "consistently ranking among the highest-value micro-markets in Tamil Nadu. "
            "The locality benefits from unmatched retail density (Ranganathan Street, Pondy Bazaar) "
            "and strong owner-occupier demand. Land values here are primarily commercial-grade."
        ),
        infra_notes=(
            "Metro Rail (Blue Line): T. Nagar station. Dense bus connectivity. "
            "Major commercial concentration drives land premiums. "
            "Retail hubs: Saravana Stores, Nalli Silks. "
            "Residential pockets: North Mada Street, GN Chetty Road command premiums."
        ),
        data_confidence=90,
        demand_drivers=["Highest commercial density in Chennai", "Metro access", "Strong investor demand", "Limited new supply"],
        risk_factors=["Extreme traffic congestion", "Limited residential-only pockets", "Premium pricing limits affordability"],
    ),

    "Chennai|Velachery": LocalityData(
        city="Chennai", locality="Velachery",
        land_rate_lo=15000, land_rate_hi=28000,
        apt_rate_lo=10000,   apt_rate_hi=16000,
        guideline_value=8500,
        trend_12m="+8.8%",
        micro_context=(
            "Velachery is a rapidly maturing residential locality in South Chennai, "
            "transitioning from a predominantly middle-class catchment to a premium destination "
            "driven by IT corridor spillover from OMR and proximity to Guindy. "
            "The area has seen significant residential development over the last decade."
        ),
        infra_notes=(
            "Metro Rail (Blue Line): Velachery terminal station. "
            "MRTS connectivity. Proximity to Pallikaranai marshland (ecological buffer — limits western expansion). "
            "Phoenix Marketcity Mall. Ramapuram IT hub accessible. "
            "Strong school belt: PSBB, DAV Velachery."
        ),
        data_confidence=85,
        demand_drivers=["Metro terminus", "IT corridor proximity", "Improving retail", "Good school belt"],
        risk_factors=["Flooding risk in low-lying pockets", "Traffic on 100 Feet Road during peak hours"],
    ),

    "Chennai|Adyar": LocalityData(
        city="Chennai", locality="Adyar",
        land_rate_lo=32000, land_rate_hi=55000,
        apt_rate_lo=18000,   apt_rate_hi=26000,
        guideline_value=12500,
        trend_12m="+4.8%",
        micro_context=(
            "Adyar is one of Chennai's most prestigious southern localities, "
            "known for its tree-lined avenues, proximity to the Adyar River estuary, "
            "and the Theosophical Society. It attracts a stable, premium demographic "
            "of senior professionals and HNIs. Price appreciation is moderate but consistent."
        ),
        infra_notes=(
            "Proximity to Besant Nagar beach and Elliot's Beach (premium lifestyle factor). "
            "Excellent connectivity to OMR IT corridor via Lattice Bridge Road. "
            "CIT Colony and Gandhi Nagar are premium sub-pockets. "
            "Kasturba Nagar apartments command ₹6,000–7,500/sq.ft carpet."
        ),
        data_confidence=86,
        demand_drivers=["Premium address", "Lifestyle quotient", "OMR proximity", "Stable HNI demand"],
        risk_factors=["Adyar River flood risk in low-lying areas", "Limited new apartment supply", "Ageing building stock in inner areas"],
    ),

    "Chennai|Porur": LocalityData(
        city="Chennai", locality="Porur",
        land_rate_lo=12000, land_rate_hi=22000,
        apt_rate_lo=8500,  apt_rate_hi=14000,
        guideline_value=7500,
        trend_12m="+10.2%",
        micro_context=(
            "Porur is an emerging residential hub in West Chennai, driven by IT park development "
            "(DLF, Ramapuram, Olympia Tech Park) and excellent NH-48 connectivity. "
            "The locality is attracting a young IT professional demographic and has seen "
            "aggressive new apartment supply from mid-segment to premium developers."
        ),
        infra_notes=(
            "NH-48 (Chennai–Bangalore Highway) frontage drives commercial premium. "
            "Proximity to Sri Ramachandra Hospital (healthcare anchor). "
            "CCTV surveillance and improved infrastructure under Chennai Corporation. "
            "Upcoming Metro Phase 2 corridor expected to pass through."
        ),
        data_confidence=82,
        demand_drivers=["IT park proximity", "NH connectivity", "Younger buyer demographic", "Improving infrastructure"],
        risk_factors=["Traffic congestion on Arcot Road", "Some areas lack civic infrastructure", "Flood-prone micro-pockets"],
    ),

    "Chennai|Perambur": LocalityData(
        city="Chennai", locality="Perambur",
        land_rate_lo=9000, land_rate_hi=16000,
        apt_rate_lo=7500,  apt_rate_hi=12000,
        guideline_value=5500,
        trend_12m="+11.8%",
        micro_context=(
            "Perambur is a densely populated North Chennai locality undergoing rapid value "
            "appreciation driven by the Perambur Metro station and improved connectivity. "
            "Traditionally a middle-income area, it is now attracting investor interest "
            "due to its affordability relative to neighbouring Anna Nagar."
        ),
        infra_notes=(
            "Perambur Metro Station (Green Line). Perambur Railway Station (suburban rail). "
            "Proximity to Kolathur, Villivakkam. "
            "High density area — limited land availability driving value appreciation."
        ),
        data_confidence=78,
        demand_drivers=["Metro station", "Affordability vs Anna Nagar", "Investor interest", "Rail connectivity"],
        risk_factors=["High density — limited open space", "Traffic congestion", "Older housing stock dominates"],
    ),

    "Chennai|Chromepet": LocalityData(
        city="Chennai", locality="Chromepet",
        land_rate_lo=10000, land_rate_hi=18000,
        apt_rate_lo=8000,  apt_rate_hi=13000,
        guideline_value=6000,
        trend_12m="+11.3%",
        micro_context=(
            "Chromepet is a well-connected South Chennai locality positioned between "
            "Pallavaram and Tambaram, benefiting from proximity to Chennai International Airport "
            "and the GST Road (NH-48) commercial corridor. It serves a mixed demographic "
            "of airport professionals, SME business owners, and first-time home buyers."
        ),
        infra_notes=(
            "Chennai International Airport: 3–5 km. GST Road (NH-48) frontage. "
            "MRTS Chromepet station. Strong bus connectivity. "
            "Proposed Metro Phase 2 alignment expected nearby."
        ),
        data_confidence=80,
        demand_drivers=["Airport proximity", "GST Road connectivity", "Affordable entry point", "Good transit links"],
        risk_factors=["Aircraft noise in some pockets", "Traffic on GST Road", "Flooding in low-lying areas"],
    ),

    "Chennai|Tambaram": LocalityData(
        city="Chennai", locality="Tambaram",
        land_rate_lo=8000, land_rate_hi=15000,
        apt_rate_lo=7000,  apt_rate_hi=11500,
        guideline_value=5500,
        trend_12m="+12.6%",
        micro_context=(
            "Tambaram is one of South Chennai's fastest-appreciating localities, "
            "driven by rapid suburban expansion, the GST Road IT corridor, "
            "and improving rail connectivity. It is a top destination for "
            "first-time buyers and investors seeking affordable Chennai real estate."
        ),
        infra_notes=(
            "Tambaram Railway Station (busy suburban rail hub). GST Road corridor. "
            "Proximity to Chromepet MRTS. New residential developments by major builders. "
            "Proposed Chennai Suburban Railway expansion will improve connectivity further."
        ),
        data_confidence=80,
        demand_drivers=["Affordability", "Rail hub", "GST Road growth", "IT corridor expansion"],
        risk_factors=["Suburban infrastructure still catching up", "Flooding risk in some areas", "Long commute to North Chennai"],
    ),

    "Chennai|Sholinganallur": LocalityData(
        city="Chennai", locality="Sholinganallur",
        land_rate_lo=16000, land_rate_hi=28000,
        apt_rate_lo=11000,   apt_rate_hi=17000,
        guideline_value=8500,
        trend_12m="+9.4%",
        micro_context=(
            "Sholinganallur is the epicentre of Chennai's OMR IT corridor, "
            "home to major tech parks (Tidel Park II, Ramanujan IT City vicinity) "
            "and a thriving residential market dominated by IT professionals. "
            "It offers a mix of builder apartments, gated communities, and villa plots."
        ),
        infra_notes=(
            "OMR (IT Expressway): central location. "
            "Proximity to Perungudi, Kandanchavadi IT hubs. "
            "Upcoming Metro Phase 2: OMR corridor alignment. "
            "Strong retail: Phoenix Marketcity (Velachery, 6km). "
            "Active apartment market from premium developers: Casagrand, Godrej, Prestige."
        ),
        data_confidence=85,
        demand_drivers=["OMR IT corridor", "Metro Phase 2 anticipation", "Premium developer supply", "Young professional demand"],
        risk_factors=["OMR traffic congestion", "Flooding risk (Pallikaranai marsh proximity)", "Supply overhang risk"],
    ),

    "Chennai|Pallavaram": LocalityData(
        city="Chennai", locality="Pallavaram",
        land_rate_lo=9500, land_rate_hi=17000,
        apt_rate_lo=7800,  apt_rate_hi=12500,
        guideline_value=5800,
        trend_12m="+10.8%",
        micro_context=(
            "Pallavaram is a strategically located South Chennai locality adjacent to "
            "Chennai International Airport, on the GST Road corridor. "
            "It serves a mix of airport industry workers, defence personnel (AAI colony), "
            "and value-seeking home buyers who want airport proximity at affordable prices."
        ),
        infra_notes=(
            "Chennai International Airport: immediate adjacency. "
            "GST Road (NH-48). AAI (Airport Authority of India) residential colony. "
            "Proposed Metro link to airport. Strong bus connectivity."
        ),
        data_confidence=79,
        demand_drivers=["Airport adjacency", "AAI employee demand", "GST Road growth", "Affordable entry"],
        risk_factors=["Aircraft noise", "Limited FSI due to airport height restrictions", "High-density area"],
    ),

    "Chennai|Shenoy Nagar": LocalityData(
        city="Chennai", locality="Shenoy Nagar",
        land_rate_lo=28000, land_rate_hi=45000,
        apt_rate_lo=14000,   apt_rate_hi=21000,
        guideline_value=11500,
        trend_12m="+5.5%",
        micro_context=(
            "Shenoy Nagar is a premium North Chennai locality known for its upscale residential "
            "character, wide streets, and established neighbourhood feel. It is adjacent to "
            "Anna Nagar but commands a slight premium due to its exclusive, lower-density character. "
            "Demand is predominantly from HNIs and senior professionals."
        ),
        infra_notes=(
            "Proximity to Anna Nagar Metro stations. "
            "Excellent connectivity to Chennai CBD (Nungambakkam, Egmore). "
            "Premium schools, hospitals, and shopping in immediate vicinity. "
            "CMDA approved residential zone."
        ),
        data_confidence=87,
        demand_drivers=["Premium address", "Low density character", "HNI demand", "Anna Nagar proximity"],
        risk_factors=["Very limited new supply", "High entry price", "Ageing housing stock"],
    ),

    # ── Bangalore ────────────────────────────────────────────────

    "Bangalore|Koramangala": LocalityData(
        city="Bangalore", locality="Koramangala",
        land_rate_lo=45000, land_rate_hi=75000,
        apt_rate_lo=17000,   apt_rate_hi=25000,
        guideline_value=14000,
        trend_12m="+9.8%",
        micro_context=(
            "Koramangala is Bangalore's most iconic residential-commercial locality, "
            "the nucleus of the city's startup ecosystem and premium residential market. "
            "1st–8th Block command varying premiums, with 1st–4th Block being most exclusive. "
            "Values here reflect Bangalore's best in terms of lifestyle, connectivity, and prestige."
        ),
        infra_notes=(
            "Central location: equidistant from CBD (Majestic), HSR Layout, and Indiranagar. "
            "Forum Mall, Koramangala 100 Feet Road commercial strip. "
            "No Metro currently (Proposed Phase 3). Strong cab/auto connectivity. "
            "Top schools: DPS, National Public School. Hospitals: Manipal, Sakra."
        ),
        data_confidence=90,
        demand_drivers=["Startup hub status", "Premium lifestyle", "Central location", "Young professional demand"],
        risk_factors=["Extreme traffic congestion", "Parking scarcity", "High entry price", "No Metro currently"],
    ),

    "Bangalore|Whitefield": LocalityData(
        city="Bangalore", locality="Whitefield",
        land_rate_lo=22000, land_rate_hi=38000,
        apt_rate_lo=11000,   apt_rate_hi=17000,
        guideline_value=9000,
        trend_12m="+12.2%",
        micro_context=(
            "Whitefield is Bangalore's premier IT corridor destination, home to ITPB, "
            "Bagmane Tech Park, and dozens of MNC campuses. It is one of the fastest-appreciating "
            "localities in South India, driven by massive IT employment and improving infrastructure. "
            "The recent Metro connection has significantly accelerated value growth."
        ),
        infra_notes=(
            "Whitefield Metro Station (Purple Line extension) — opened 2023, game-changer for the area. "
            "ITPB (International Tech Park Bangalore). Bagmane Tech Park. "
            "Phoenix Marketcity Mall. Strong developer activity: Prestige, Brigade, Sobha. "
            "STRR (Satellite Town Ring Road) connectivity improving."
        ),
        data_confidence=88,
        demand_drivers=["IT park density", "Metro connectivity (recent)", "Premium developer supply", "NRI investor demand"],
        risk_factors=["Traffic congestion on Old Madras Road", "Flooding in low-lying areas", "Supply overhang risk from excess apartments"],
    ),

    "Bangalore|Indiranagar": LocalityData(
        city="Bangalore", locality="Indiranagar",
        land_rate_lo=50000, land_rate_hi=80000,
        apt_rate_lo=18000,   apt_rate_hi=28000,
        guideline_value=15000,
        trend_12m="+8.4%",
        micro_context=(
            "Indiranagar is Bangalore's most lifestyle-driven premium locality, "
            "known for its vibrant F&B scene (100 Feet Road, 12th Main), boutique retail, "
            "and high concentration of expats and senior IT professionals. "
            "Values here are driven more by lifestyle demand than IT proximity."
        ),
        infra_notes=(
            "Indiranagar Metro Station (Purple Line). 100 Feet Road commercial strip. "
            "HAL Airport Road connectivity. Proximity to Defence Colony, Domlur. "
            "CMH Road (hospital corridor). "
            "High rental yields: 2.8–3.5% for premium apartments."
        ),
        data_confidence=89,
        demand_drivers=["Lifestyle premium", "Metro station", "Expat demand", "HAL proximity"],
        risk_factors=["Very high land values limit new residential development", "Traffic on 100 Feet Road", "Limited parking"],
    ),

    "Bangalore|HSR Layout": LocalityData(
        city="Bangalore", locality="HSR Layout",
        land_rate_lo=32000, land_rate_hi=50000,
        apt_rate_lo=13000,   apt_rate_hi=19000,
        guideline_value=11000,
        trend_12m="+10.9%",
        micro_context=(
            "HSR Layout (Hosur-Sarjapur Road Layout) is a meticulously planned locality "
            "that has become Bangalore's second startup hub after Koramangala. "
            "It offers planned sector-wise development, wide roads, and proximity to "
            "both Outer Ring Road IT companies and Electronic City."
        ),
        infra_notes=(
            "Outer Ring Road (ORR) frontage — access to Marathahalli, Bellandur IT hubs. "
            "HSR Layout BDA planned sector grid (Sectors 1–7). "
            "Proposed Metro Phase 3 alignment. "
            "Strong retail: Decathlon, large-format stores on 27th Main."
        ),
        data_confidence=86,
        demand_drivers=["Startup ecosystem", "Planned layout", "ORR connectivity", "Young professional demand"],
        risk_factors=["ORR traffic congestion", "No Metro currently", "Premium pricing"],
    ),

    "Bangalore|Marathahalli": LocalityData(
        city="Bangalore", locality="Marathahalli",
        land_rate_lo=18000, land_rate_hi=32000,
        apt_rate_lo=10000,   apt_rate_hi=16000,
        guideline_value=8500,
        trend_12m="+13.5%",
        micro_context=(
            "Marathahalli is the highest-appreciating mid-segment locality in Bangalore, "
            "driven by its position at the intersection of ORR, Whitefield, and Varthur. "
            "It serves a large IT workforce with affordable-to-mid segment housing. "
            "New developer activity is strong, and the upcoming Metro is a significant catalyst."
        ),
        infra_notes=(
            "Marathahalli Bridge: major ORR junction. "
            "Bagmane Tech Park: 3 km. ITPB: 8 km. "
            "Proposed Metro Phase 2A/B: Marathahalli station. "
            "Forum Shantiniketan Mall, Inorbit Mall nearby."
        ),
        data_confidence=84,
        demand_drivers=["ORR IT corridor", "Metro anticipation", "Affordability", "High rental demand"],
        risk_factors=["Severe traffic congestion at Marathahalli Bridge", "Flooding risk (Varthur lake proximity)", "Noise from ORR"],
    ),

    "Bangalore|Electronic City": LocalityData(
        city="Bangalore", locality="Electronic City",
        land_rate_lo=12000,  land_rate_hi=22000,
        apt_rate_lo=8500,   apt_rate_hi=13500,
        guideline_value=7000,
        trend_12m="+15.0%",
        micro_context=(
            "Electronic City is Bangalore's original IT hub — home to Infosys, Wipro, "
            "HCL, and 200+ companies across Phase 1 and Phase 2. Despite its peripheral location, "
            "it is the highest-appreciating locality in our dataset due to the recent Metro "
            "connection and massive IT employment base (200,000+ jobs within 5 km)."
        ),
        infra_notes=(
            "Electronic City Metro Station (Green Line) — opened 2024. "
            "Hosur Road (NH-44): 25 km to city center. "
            "NICE Road elevated expressway. "
            "Electronic City Phase 1 and Phase 2 tech parks. "
            "Proposed Peripheral Ring Road will significantly improve connectivity."
        ),
        data_confidence=83,
        demand_drivers=["IT employment density", "Metro connection (new)", "Affordability", "NICE Road expressway"],
        risk_factors=["Distance from city centre", "Hosur Road traffic", "Limited retail options vs other localities"],
    ),

    
}

# ── Lookup helpers ────────────────────────────────────────────────

def get_locality(city: str, locality: str) -> Optional[LocalityData]:
    """Get locality data by city and locality name."""
    key = f"{city}|{locality}"
    data = LOCALITY_DB.get(key)
    if data:
        return data
    # Fuzzy match: try partial key
    city_lower = city.lower()
    loc_lower  = locality.lower()
    for k, v in LOCALITY_DB.items():
        if city_lower in k.lower() and loc_lower in k.lower():
            return v
    return None

def get_confidence_label(score: int) -> str:
    if score >= 85: return "High"
    if score >= 70: return "Good"
    if score >= 55: return "Moderate"
    return "Low"

def list_localities(city: str) -> list[str]:
    """Return all known localities for a city."""
    return [
        v.locality for k, v in LOCALITY_DB.items()
        if v.city.lower() == city.lower()
    ]

# ── Import for type hint ──────────────────────────────────────────
from typing import Optional
