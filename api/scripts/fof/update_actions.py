import json, re

path = r"C:\Dev\rbgg\api\configs\fof\fields_of_fire_actions.json"
with open(path, encoding="utf-8") as f:
    actions = json.load(f)

originator_map = {
    "CO HQ, BN HQ": "co_or_bn_hq",
    "Any HQ or Staff": "any_hq_or_staff",
    "CO HQ or CO Staff": "co_hq_or_co_staff",
    "BN HQ or CO Staff": "bn_hq_or_co_staff",
    "CO HQ": "co_hq",
    "PLT HQ": "plt_hq",
    "Any HQ or Staff on the same card as the cut line": "same_card_hq_or_staff",
    "CO HQ or CO Staff (or PLT HQ in a single-platoon mission)": "co_hq_or_co_staff_or_plt_hq",
}

def draw_count(value):
    if value == "Auto":
        return 0
    if value == "Cover # (+/–)":
        return "cover"
    if value == "Per mission instructions (+/–)":
        return "mission"
    m = re.search(r"\d+", value)
    return int(m.group()) if m else 0

def success_icon(details):
    for icon in ("Crosshairs", "Grenade", "Rally", "Burst", "Cover", "Infiltrate"):
        if icon in details:
            return icon.lower()
    return None

def miss_modifier(details):
    m = re.search(r"([A-Za-z ]+?) Miss Modifier", details)
    return m.group(1).strip() + " Miss Modifier" if m else None

def ammo_type(action):
    aid = action["id"]
    details = action["details"]
    if aid == "flamethrower_attack":
        return "f"
    if aid in ("attempt_to_throw_a_demolition_charge", "place_a_demolition_charge"):
        return "demo"
    if aid == "attempt_to_concentrate_fire":
        return "mg"
    return None

for action in actions:
    if "friendly_command" not in (action.get("phases") or []):
        continue
    details = action.get("details", "")
    aid = action["id"]
    action["originator_type"] = originator_map.get(action.get("originator"), "any_hq_or_staff")
    action["recipient_type"] = action.get("recipient")
    action["communication_required"] = True
    action["los_required"] = "LOS" in details
    action["draw_count"] = draw_count(action.get("draw", "Auto"))
    action["success_icon"] = success_icon(details)
    action["miss_modifier"] = miss_modifier(details)
    action["ammo_type"] = ammo_type(action)
    action["ammo_cost"] = 2 if aid == "attempt_to_concentrate_fire" else (1 if ammo_type(action) in ("demo", "f") else 0)
    if aid == "attempt_to_call_for_fire_from_an_off_map_firing_agency_includes_air_strikes_and_attack_helicopters":
        action["fire_mission_type"] = "HE"
    elif aid == "call_for_indirect_fire_from_an_on_map_mortar":
        action["fire_mission_type"] = "HE"
    else:
        action["fire_mission_type"] = None
    action["auto_if_no_vof"] = "Auto if no VOF" in action.get("draw", "")

with open(path, "w", encoding="utf-8") as f:
    json.dump(actions, f, indent=2, ensure_ascii=False)
    f.write("\n")
print("updated", sum(1 for a in actions if "friendly_command" in (a.get("phases") or [])))
