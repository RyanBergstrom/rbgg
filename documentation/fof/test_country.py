import re
from pathlib import Path

# Test country detection
COUNTRY_PREFIX_MAP = {
    "1atf": "Australian",
    "us": "US",
    "german": "German",
    "nkpa": "NKPA",
    "vietcong": "VietCong",
    "nva": "NVA",
    "arvn": "ARVN",
}

COUNTRY_PATTERN_MAP = {
    "2para": "Commonwealth",
    "para": "Commonwealth",
    "parachute": "Commonwealth",
    "vc": "VietCong",
    "vietcong": "VietCong",
    "viet minh": "VietCong",
    "nva": "NVA",
    "north vietnam": "NVA",
    "us": "US",
    "1atf": "Australian",
    "ger": "German",
    " Wehrmach": "German",
    "bw": "German",
    "nkpa": "NKPA",
    "north korea": "NKPA",
    "arvn": "ARVN",
    "south vietnam": "ARVN",
}

# Test stems
test_names = [
    "VC LAT Asslt Team.png",
    "2PARA LAT Cas 2.png",
    "1_1 3 step.png",
    "1ATF 10-2b.jpg",
    "Ammo MG 2.png",
    "NKPA LAT Casualty 1.png",
    "PC C.png",
    "Tiger 111.png",
    "Commands GySGT complete.png",
    "Commands Tank PLT complete.png",
    "Control_FPF-Mortar.png",
    "Control_Route Point 2.png",
    "Control_Target AB1003.png",
    "Fire Mission -7 Iincoming.png",
    "Marker - WP.png",
    "Vol3 - Assets - Smoke - Screening b.png",
]

COUNTRY_SUFFIX_MAP = {
    "australian": "Australian",
    "us": "US",
    "german": "German",
    "north vietnam": "NVA",
    "viet cong": "VietCong",
    "north korea": "NKPA",
    "south vietnam": "ARVN",
    "commonwealth": "Commonwealth",
}

for name in test_names:
    stem = Path(name).stem.lower()
    hints = {}
    
    # Check prefix
    for prefix, country in COUNTRY_PREFIX_MAP.items():
        if stem.startswith(prefix):
            hints["country"] = country
            break
    
    # Check pattern
    if "country" not in hints:
        for pattern, country in COUNTRY_PATTERN_MAP.items():
            if pattern in stem:
                hints["country"] = hints.get("country") or country
                break
    
    # Check suffix keywords
    if "country" not in hints:
        for kw, country in COUNTRY_SUFFIX_MAP.items():
            if kw in stem:
                hints["country"] = hints.get("country") or country
                break
    
    print(f"{name:40s} -> country={hints.get('country', 'Unknown')} stem='{stem}'")