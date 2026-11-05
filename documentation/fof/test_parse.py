import re
from pathlib import Path

test_names = [
    "1_1 3 step.png",
    "1ATF 10-2b.jpg",
    "2PARA LAT Cas 2.png",
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
    "vc": "VietCong",
    "vietcong": "VietCong",
    "nva": "NVA",
}

SIDE_SUFFIX_MAP = {
    "b": "back",
    "f": "front",
    "al": "alternate",
}

for name in test_names:
    stem = Path(name).stem.lower()
    hints = {}
    
    # Country
    for prefix, country in COUNTRY_PREFIX_MAP.items():
        if stem.startswith(prefix):
            hints["country"] = country
            break
    if "country" not in hints:
        for pattern, country in COUNTRY_PATTERN_MAP.items():
            if pattern in stem:
                hints["country"] = hints.get("country") or country
                break
    
    # Side
    for suffix, side in SIDE_SUFFIX_MAP.items():
        if stem.endswith(" " + suffix) or stem.endswith(suffix):
            hints["side"] = side
            break
    
    # Steps
    m = re.search(r"(\d+)\s*step", stem)
    if m:
        hints["steps_total"] = int(m.group(1))
    
    # Unit type hints
    if re.search(r"\blat\b", stem) or re.search(r"\bL-AT\b", stem):
        hints["unit_type_hint"] = "lat"
    if re.search(r"\b(sqd|squad|fire team|ft)\b", stem):
        hints["unit_type_hint"] = hints.get("unit_type_hint") or "squad"
    
    # Marker type hints
    if re.search(r"\bvof\b", stem):
        hints["marker_type_hint"] = "vof"
    elif re.search(r"\bpdf\b|primary direction", stem):
        hints["marker_type_hint"] = "pdf"
    elif re.search(r"\bexposed\b", stem):
        hints["marker_type_hint"] = "exposed"
    elif re.search(r"\bpin(ned)?\b", stem):
        hints["marker_type_hint"] = "pin"
    elif re.search(r"\bconcentrated fire\b", stem):
        hints["marker_type_hint"] = "concentrated_fire"
    elif re.search(r"\bcrossfire\b", stem):
        hints["marker_type_hint"] = "crossfire"
    elif re.search(r"\btactical control\b", stem):
        hints["marker_type_hint"] = "tactical_control"
    elif re.search(r"\bcover\b", stem):
        hints["marker_type_hint"] = "cover"
    elif re.search(r"\bammo\b", stem):
        hints["marker_type_hint"] = "ammo"
    elif re.search(r"\bpotential contact\b|pc\b", stem):
        hints["marker_type_hint"] = "potential_contact"
    elif re.search(r"\bcurrent activity\b", stem):
        hints["marker_type_hint"] = "current_activity"
    elif re.search(r"\bvisibility\b", stem):
        hints["marker_type_hint"] = "visibility"
    
    # Weapon hints
    weapon_keywords = {
        "bazooka": "Bazooka",
        "106mm": "106mm Recoilless Rifle",
        "wpns": "Weapons Team",
        "aslt": "Assault Team",
        "mortar": "Mortar",
        "mg": "Machine Gun",
        "csm": "Company Sergeant Major",
    }
    for kw, wtype in weapon_keywords.items():
        if kw in stem:
            hints["weapon_type"] = wtype
            break
    
    c = hints.get('country') or '?'
    s = hints.get('side') or '?'
    st = hints.get('steps_total') if hints.get('steps_total') is not None else '?'
    u = hints.get('unit_type_hint') or '?'
    mk = hints.get('marker_type_hint') or '?'
    w = hints.get('weapon_type') or '?'
    print(f"{name:40s} -> country={c!s:8s} side={s!s:6s} steps={st!s:4s} unit_type={u!s:12s} marker_type={mk!s:12s} weapon={w!s:15s}")