"""
valUProp.in — Locality DB Generator
scripts/generate_locality_db.py

WEEKLY REFRESH WORKFLOW:
1. Prabhakar uploads fresh chennai_cma_locality_seed.csv
2. Run: python3 generate_locality_db.py <csv_path>
3. Output: backend/locality_db.py (ready to deploy)

Usage:
    python3 generate_locality_db.py chennai_cma_locality_seed.csv
    python3 generate_locality_db.py  # uses default path

This ensures locality_db.py is ALWAYS in sync with the CSV seed.
"""

import csv
import sys
import os
from datetime import datetime

CSV_PATH    = sys.argv[1] if len(sys.argv) > 1 else "chennai_cma_locality_seed.csv"
OUTPUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "locality_db.py"

# Tier → trend mapping
TIER_TREND = {
    'GCC':           '+5.5%',
    'Avadi Corp':    '+7.5%',
    'Tambaram Corp': '+7.5%',
    'CMA':           '+13.0%',
}

# Confidence → score
CONF_SCORE = {'high': 82, 'medium': 72, 'low': 60}

# Zone → micro-market context
ZONE_CONTEXT = {
    'Zone 1 - Thiruvottiyur': "North Chennai coastal locality with suburban rail connectivity. Industrial and port-adjacent demand.",
    'Zone 2 - Manali':        "North Chennai industrial zone. Petrochemical and manufacturing belt. Limited residential premium.",
    'Zone 3 - Madhavaram':    "North Chennai growing corridor. Metro Phase 2 station proposed. Affordable mid-segment demand.",
    'Zone 4 - Tondiarpet':    "North Chennai established locality. Port Trust proximity. Mixed residential-commercial.",
    'Zone 5 - Royapuram':     "North Chennai heritage and commercial zone. Proximity to Chennai Port and George Town.",
    'Zone 6 - Thiru Vi Ka Nagar': "Mid-Chennai established residential. Perambur metro connectivity. Mid-segment demand.",
    'Zone 7 - Ambattur':      "West Chennai industrial-residential corridor. Ambattur Industrial Estate employment anchor.",
    'Zone 8 - Anna Nagar':    "Premium North-West Chennai. Anna Nagar metro (Green Line). Top schools, hospitals, and retail.",
    'Zone 9 - Teynampet':     "Prime Central Chennai. T.Nagar retail, Nungambakkam commercial. Highest value GCC zone.",
    'Zone 10 - Kodambakkam':  "West Chennai established. Good metro access. Strong school and hospital belt.",
    'Zone 11 - Valasaravakkam': "West Chennai residential corridor. NH-48 access. IT park proximity (Porur, Ramapuram).",
    'Zone 12 - Alandur':      "South Chennai GCC zone. Airport adjacent. Good MRTS and GST Road access.",
    'Zone 13 - Adyar':        "Premium South Chennai. Beach proximity, Theosophical Society. HNI and premium demand.",
    'Zone 14 - Perungudi':    "OMR IT corridor. Premium apartments, IT park demand. High appreciation zone.",
    'Zone 15 - Sholinganallur': "OMR South. Active IT corridor. Metro Phase 2 planned. Strong appreciation.",
    'Avadi Corporation':      "Avadi Corp zone. North-West suburban belt. Affordable to mid-segment. Defence and SME workforce.",
    'Tambaram Corporation':   "South Chennai suburban. GST Road corridor. Airport proximity. First-home buyer zone.",
    'CMA':                    "Chennai Metropolitan Area outskirts. Peripheral growth zone. Infrastructure-driven appreciation.",
}

def generate(csv_path: str, output_path: str):
    # Read CSV
    rows = []
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Group by locality
    localities = {}
    for row in rows:
        loc = row['locality'].strip()
        if loc not in localities:
            localities[loc] = {
                'pincode':       row['pincode'].strip(),
                'confidence':    row['confidence'].strip(),
                'gcc_zone':      row['gcc_zone'].strip(),
                'boundary_tier': row['boundary_tier'].strip(),
            }
        pt = row['property_type'].strip()
        if pt == 'flat':
            localities[loc]['apt_lo']    = int(row['rate_min'])
            localities[loc]['apt_mid']   = int(row['rate_mid'])
            localities[loc]['apt_hi']    = int(row['rate_max'])
            localities[loc]['guideline'] = int(row['guideline_value']) if row.get('guideline_value','').strip() else 0
        elif pt == 'land':
            localities[loc]['land_lo']   = int(row['rate_min'])
            localities[loc]['land_mid']  = int(row['rate_mid'])
            localities[loc]['land_hi']   = int(row['rate_max'])

    # Build output
    lines = []
    lines.append('"""')
    lines.append('valUProp.in — Locality Price Database')
    lines.append('locality_db.py')
    lines.append('')
    lines.append('AUTO-GENERATED — do not edit manually.')
    lines.append(f'Source: {os.path.basename(csv_path)}')
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'Localities: {len(localities)} Chennai + Bangalore')
    lines.append('"""')
    lines.append('')
    lines.append('from dataclasses import dataclass, field')
    lines.append('from typing import Optional')
    lines.append('')
    lines.append('@dataclass')
    lines.append('class LocalityData:')
    lines.append('    city:              str')
    lines.append('    locality:          str')
    lines.append('    land_rate_lo:      float')
    lines.append('    land_rate_hi:      float')
    lines.append('    apt_rate_lo:       float')
    lines.append('    apt_rate_hi:       float')
    lines.append('    guideline_value:   float')
    lines.append('    trend_12m:         str')
    lines.append('    micro_context:     str')
    lines.append('    infra_notes:       str')
    lines.append('    data_confidence:   int   = 75')
    lines.append('    demand_drivers:    list  = field(default_factory=list)')
    lines.append('    risk_factors:      list  = field(default_factory=list)')
    lines.append('')
    lines.append('LOCALITY_DB: dict[str, LocalityData] = {')
    lines.append(f'    # ── Chennai ({len(localities)} localities from CSV) ─────────────────────────')
    lines.append('')

    for loc, d in localities.items():
        apt_lo  = d.get('apt_lo',  5000)
        apt_hi  = d.get('apt_hi',  8000)
        land_lo = d.get('land_lo', apt_lo)
        land_hi = d.get('land_hi', apt_hi)
        guide   = d.get('guideline', 0)
        pin     = d['pincode']
        conf    = CONF_SCORE.get(d['confidence'], 65)
        trend   = TIER_TREND.get(d['boundary_tier'], '+8.0%')
        zone    = d['gcc_zone']
        tier    = d['boundary_tier']
        micro   = ZONE_CONTEXT.get(zone, f"{loc} is a residential locality in Chennai, {zone}.")
        micro_full = f"{loc}: {micro}"
        infra   = f"Pincode {pin}. {tier} zone. {zone}."

        lines.append(f'    "Chennai|{loc}": LocalityData(')
        lines.append(f'        city="Chennai", locality="{loc}",')
        lines.append(f'        land_rate_lo={land_lo}, land_rate_hi={land_hi},')
        lines.append(f'        apt_rate_lo={apt_lo},  apt_rate_hi={apt_hi},')
        lines.append(f'        guideline_value={guide},')
        lines.append(f'        trend_12m="{trend}",')
        lines.append(f'        micro_context="{micro_full}",')
        lines.append(f'        infra_notes="{infra}",')
        lines.append(f'        data_confidence={conf},')
        lines.append(f'        demand_drivers=["Residential demand", "{zone}", "Chennai growth"],')
        lines.append(f'        risk_factors=["Verify {tier} approvals before purchase"],')
        lines.append(f'    ),')
        lines.append('')

    # Bangalore (hardcoded — update manually or add blr_seed.csv)
    lines.append('    # ── Bangalore ────────────────────────────────────────────────────')
    lines.append('')
    blr = [
        ('Indiranagar',57000,67000,21200,24800,15000,'+8.4%','Premium lifestyle locality. Expat demand. F&B hub.','Indiranagar Metro Station (Purple Line).',89),
        ('Koramangala',53400,62600,19300,22700,14000,'+9.8%','Startup hub and premium residential nucleus.','Forum Mall. Metro Phase 3 proposed.',90),
        ('Whitefield',26700,31300,12900,15100,9000,'+12.2%','Premier IT corridor. ITPB, Bagmane Tech Park.','Whitefield Metro Station (Purple Line, 2023).',88),
        ('HSR Layout',36800,43200,14700,17300,11000,'+10.9%','Second startup hub. Planned grid. ORR access.','ORR frontage. Metro Phase 3 proposed.',86),
        ('Marathahalli',22100,25900,12000,14000,8500,'+13.5%','Highest-appreciating mid-segment. ORR junction.','Marathahalli Bridge. Metro proposed.',84),
        ('Electronic City',15200,17800,10100,11900,7000,'+15.0%','Original IT hub. Infosys/Wipro/HCL. 200k+ jobs.','Electronic City Metro (Green Line, 2024).',83),
        ('JP Nagar',22000,26000,10500,13500,8000,'+7.8%','Established South Bangalore. Good school belt.','NICE Road. Metro Phase 3.',80),
        ('BTM Layout',20000,24000,9500,12500,7500,'+12.1%','Dense residential near Koramangala.','ORR. Silk Board junction.',78),
        ('Hebbal',24000,28000,11000,14000,8500,'+11.3%','North Bangalore. Lake-front premium.','Hebbal flyover. BIAL road.',80),
        ('Yelahanka',16000,20000,8500,11500,6500,'+14.2%','Fast-growing North suburb near airport.','BIAL Airport 15km. Metro proposed.',76),
        ('Sarjapur Road',24000,28000,11500,14500,9000,'+12.5%','Major East Bangalore IT corridor.','ORR-Sarjapur junction.',82),
        ('Bellandur',26000,30000,12500,15500,9500,'+12.0%','Premium East Bangalore. ORR access.','ORR. Bellandur lake.',80),
        ('KR Puram',18000,22000,9000,12000,7000,'+13.5%','East Bangalore affordable. Metro drives appreciation.','KR Puram Metro (Purple Line).',78),
        ('Hennur',16000,20000,8500,11500,6500,'+13.2%','North-East emerging corridor.','Metro Phase 2 proposed. ORR.',76),
    ]
    for e in blr:
        loc,ll,lh,al,ah,gv,trend,ctx,infra,conf = e
        lines.append(f'    "Bangalore|{loc}": LocalityData(')
        lines.append(f'        city="Bangalore", locality="{loc}",')
        lines.append(f'        land_rate_lo={ll}, land_rate_hi={lh},')
        lines.append(f'        apt_rate_lo={al},  apt_rate_hi={ah},')
        lines.append(f'        guideline_value={gv},')
        lines.append(f'        trend_12m="{trend}",')
        lines.append(f'        micro_context="{ctx}",')
        lines.append(f'        infra_notes="{infra}",')
        lines.append(f'        data_confidence={conf},')
        lines.append(f'        demand_drivers=["Residential demand", "Bangalore IT growth"],')
        lines.append(f'        risk_factors=["Verify BBMP khata and E-khata before purchase"],')
        lines.append(f'    ),')
        lines.append('')

    lines.append('}')
    lines.append('')
    lines.append('def get_locality(city: str, locality: str) -> Optional[LocalityData]:')
    lines.append('    key = f"{city}|{locality}"')
    lines.append('    data = LOCALITY_DB.get(key)')
    lines.append('    if data: return data')
    lines.append('    for k, v in LOCALITY_DB.items():')
    lines.append('        if city.lower() in k.lower() and locality.lower() in k.lower():')
    lines.append('            return v')
    lines.append('    return None')
    lines.append('')
    lines.append('def get_confidence_label(score: int) -> str:')
    lines.append('    if score >= 85: return "Strong"')
    lines.append('    if score >= 70: return "Good"')
    lines.append('    if score >= 60: return "Fair"')
    lines.append('    return "Weak"')
    lines.append('')
    lines.append('def list_localities(city: str) -> list[str]:')
    lines.append('    return [v.locality for k, v in LOCALITY_DB.items() if v.city.lower() == city.lower()]')
    lines.append('')
    lines.append('from typing import Optional')

    content = '\n'.join(lines)
    with open(output_path, 'w') as f:
        f.write(content)

    import ast
    ast.parse(content)
    print(f"Generated {output_path}: {len(localities)} Chennai + {len(blr)} Bangalore localities")
    return len(localities)

if __name__ == '__main__':
    n = generate(CSV_PATH, OUTPUT_PATH)
    print(f"Done. Deploy backend/{OUTPUT_PATH} to GitHub.")
