"""
ValUprop.in — Static Fallback Price Data
backend/fallback_data.py

Used when:
  1. LLM call fails (API down, timeout)
  2. Locality not found in locality_db.py
  3. DEV_MODE=true (no API keys)

Format per entry: (min_L, max_L, sqft_rate, trend_12m)
All prices in Indian Lakhs.
Last manually reviewed: April 2025.
"""

from typing import Optional


_FALLBACK: dict = {
    "Chennai": {
        # Locality              min    max   sqft   trend
        "Anna Nagar":          (48,   74,   4850,  "+6.2%"),
        "T. Nagar":            (55,   88,   5200,  "+7.5%"),
        "Velachery":           (38,   60,   4100,  "+8.8%"),
        "Adyar":               (60,   95,   5400,  "+4.8%"),
        "Porur":               (32,   52,   3700,  "+10.2%"),
        "Perambur":            (26,   44,   3200,  "+11.8%"),
        "Chromepet":           (28,   46,   3400,  "+11.3%"),
        "Tambaram":            (24,   40,   3100,  "+12.6%"),
        "Sholinganallur":      (44,   68,   4400,  "+9.4%"),
        "Pallavaram":          (27,   45,   3300,  "+10.8%"),
        "Shenoy Nagar":        (60,   95,   5600,  "+5.5%"),
        "Mylapore":            (55,   85,   5100,  "+5.0%"),
        "Nungambakkam":        (65,  105,   5800,  "+4.5%"),
        "Mogappair":           (35,   58,   4200,  "+9.1%"),
        "Kilpauk":             (50,   80,   4800,  "+6.0%"),
    },
    "Bangalore": {
        "Koramangala":         (70,  110,   6100,  "+9.8%"),
        "Whitefield":          (52,   85,   5200,  "+12.2%"),
        "Indiranagar":         (75,  118,   6300,  "+8.4%"),
        "Jayanagar":           (65,  102,   5700,  "+7.4%"),
        "HSR Layout":          (60,   96,   5500,  "+10.9%"),
        "Marathahalli":        (45,   72,   4700,  "+13.5%"),
        "BTM Layout":          (48,   78,   4900,  "+12.1%"),
        "Electronic City":     (35,   58,   4200,  "+15.0%"),
        "Yelahanka":           (38,   62,   4300,  "+14.2%"),
        "Hebbal":              (56,   90,   5300,  "+11.3%"),
    },
}

# BHK multipliers applied on top of base 2BHK price
_BHK_MULT = {
    "1BHK":  0.58,
    "2BHK":  1.00,
    "3BHK":  1.45,
    "4BHK":  1.90,
    "5BHK+": 2.40,
}

# Property type multipliers relative to Apartment base
_TYPE_MULT = {
    "Apartment":       1.00,
    "IndependentHouse":5.50,   # land-led — higher base in lakhs
    "Villa":           8.00,
    "LandPlot":        2.20,
}


def get_fallback(city: str, locality: str, prop_type: str = "Apartment",
                 bhk: str = "2BHK") -> dict:
    """
    Return a fallback price dict for the given parameters.
    Returns: { min, max, sqft, trend }  (all in Lakhs)
    """
    city_data = _FALLBACK.get(city, _FALLBACK.get("Chennai", {}))

    # Try exact match first
    row = city_data.get(locality)

    # Try partial/fuzzy match
    if not row:
        for key, val in city_data.items():
            if locality.lower() in key.lower() or key.lower() in locality.lower():
                row = val
                break

    # Default if nothing found
    if not row:
        row = (35, 60, 4200, "+8.0%")

    base_min, base_max, sqft, trend = row

    # Apply property-type multiplier for non-apartment types
    if prop_type != "Apartment":
        m = _TYPE_MULT.get(prop_type, 1.0)
        base_min = round(base_min * m, 1)
        base_max = round(base_max * m, 1)
    else:
        # Apply BHK multiplier for apartments
        m = _BHK_MULT.get(bhk, 1.0)
        base_min = round(base_min * m, 1)
        base_max = round(base_max * m, 1)

    return {
        "min":   max(base_min, 5.0),
        "max":   max(base_max, base_min * 1.25),
        "sqft":  sqft,
        "trend": trend,
    }
