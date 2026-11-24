# Fields of Fire — Card Schema & Classification Reference

## Overview

In *Fields of Fire* (GMT Games), cards are divided into functional decks spanning multiple game volumes and historical campaigns:

1. **Terrain Cards**: Form the physical card grid / map for missions (Section 2.1 & 5.0).
2. **Action Deck Cards**: Generate random events, action attempts, commands/initiative, combat hit resolution, and scatter (Section 2.8 & 6.4).
3. **Fire Support Areas (FSA)**: Off-map holding areas for artillery, mortars, and air support assets.
4. **Staging Areas**: Off-map muster zones where units begin or arrive before entering combat cards.
5. **Utility & Reference Cards**: Reshuffle cards, tactical aids (e.g. *Keep Up The Fire*), starter mission setups, and card backs.

---

## Card Schema Reference

### Top-Level Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier, e.g. `FOF-TERRAIN-N01-HILL`, `FOF-ACTION-025`, `FOF-FSA-01`. |
| `name` | string | Display title (e.g. `Hill`, `Action Card #25`, `Surf Zone`). |
| `card_type` | enum | `terrain`, `action`, `fsa`, `staging_area`, `utility`. |
| `deck` | string | Deck name (e.g. `Normandy Terrain`, `Action Deck`, `Fire Support Areas`). |
| `expansion` | enum | `Volume I`, `Volume II`, `Volume III`, `Base / Shared`, `Unknown`. |
| `purpose` | string | Functional purpose in mission or rules. |
| `image` | object | Filename, pixel dimensions, and image format. |
| `terrain_details` | object / null | Populated for `card_type == 'terrain'`. |
| `action_details` | object / null | Populated for `card_type == 'action'`. |
| `classification` | object | Review status, reviewer timestamp, and notes. |

---

## Decks by Expansion / Volume

### Volume I (9th Infantry Regiment)
- **Normandy Terrain Deck**: Cards `N01` through `N55` (Bocage, Orchard, Village, Hills, Woods, Open Fields).
- **Korea Terrain Deck**: Cards `K01` through `K55` (Hills, Rice Paddies, Rocky, Brush, Gully).
- **Heartbreak Ridge Overlay**: Cards `HBR1` through `HBR11` (Steep elevation terrain overlays +2 to +5).
- **Vietnam Terrain Deck**: Cards `V01` through `V55` (Jungle, Elephant Grass, Rubber Plantation, Bamboo, Rice Paddy).
- **Action Deck**: 50 Action cards + Reshuffle card.

### Volume II (5th Marine Regiment)
- **Peleliu Terrain Deck**: Cards `P01` through `P55` (Surf Zone, Beach, Dunes, Palm Grove, Airfield, Coral Ridge, Coral Caves).
- **Chosin Reservoir Terrain Deck**: Cards `C01` through `C55` (Snow, Frozen Ground, Heights, Bitter Cold conditions).
- **Hue City Terrain Deck**: Cards `Hue01` through `Hue55` (Urban Streets, Citadel, Multi-story buildings, Rubble).
- **Ardennes / Bulge Terrain Deck**: Cards `A01` through `A55` (Forest Road, Scrub Forest, Embankment, Village, Snow).

### Volume III (British Parachute Regiment — Falklands)
- **Goose Green Terrain Deck**: Peat, Settlement, Gorse, Ridge.
- **Fire Support Areas (FSA)**: Cards `01` through `11`.
- **Staging Areas**: Cards `01` through `11`.

---

## Terrain Details Attributes (Section 5.0)

- **Cover High / Low**: Cover ratings for units under high or low cover markers (+0 to +4).
- **Burst Modifier**: Impact on explosive and artillery attacks (-1, 0, +1).
- **Elevation**: Relative vertical contour (-1 Gully/Canal, 0 Open, +1 Hill, +2 to +5 High Ridges/Peaks).
- **Landing Zone (LZ)**: LZ-1, LZ-2, Good, Poor, or None for helicopter insertion.
- **Trafficability**: Vehicle and infantry transit ease (`good`, `fair`, `poor`, `impassable`).
- **Cover Potential**: Numerical capacity for digging foxholes or improving positions (0 to 4).
- **Borders**: North, East, South, and West edge types (`white` open, `dark` obstructed, `road`, `river`, `cliff`).
- **Features**: Tags for special card traits (`Road`, `Stream`, `Canal`, `Multi-Story`, `Cave Potential`, `Restricted LOS`).

---

## Action Details Attributes (Section 2.8 & 6.4)

Action Cards serve simultaneously across combat resolution, skill/action checks, command point generation, random events, and fire support:

- **Card Number**: Upper-right (1 through 50).
- **Activated Commands**: Upper-left inside helmet icon (1 to 6; command draws added to available pool).
- **Initiative Commands**: Directly below helmet inside square box (1 to 4; who acts first, initiative challenges).
- **Action Attempt Header**: Top-center success word (`Cover`, `Rally`, `Contact`, or null).
- **Center Action Attempt Icons (Boolean Flags)**:
  - `spot_concentrate_fire`: Crosshair / Target reticle — successful attempt to Spot or Concentrate Fire.
  - `infiltrate`: Three infantry silhouettes crawling through wire — successful attempt to Infiltrate.
  - `grenade`: Hand grenade — successful attempt to make a Grenade Attack.
  - `call_for_fire`: Single explosion burst — successful attempt to Call for Fire and triggered mine.
  - `battalion_fire_mission`: Triple explosion bursts — Call for Fire, triggered mine, and possibility of Battalion Fire Mission.
  - `call_for_fire_short`: Explosion with "Short!" text — Call for Fire has gone off-target; also indicates triggered mine.
  - `hq_event`: Radio handset with "HQ" text — Higher HQ Event.
  - `jam`: Crosshair target reticle with "Jam!" text — catastrophic failure during ranged Grenade / Missile Launcher / Concentrating Fire.
- **Anti-Tank Number**: Lower-right tank target reticle (`AT 5` to `AT 10`).
- **Combat Resolution**: Left column direct-fire table (-4 to +6 with HIT, PIN, or MISS distribution).
- **Hit Effects**: Store only the three outcome codes, in **Vet, Line, Green** order (e.g. `CC CC CC`); do not include the table title or column labels. Use `?` for an unreadable code.
- **Random Number Matrix**: Bottom row probability matrix (values 2–12 mapped to random outcome numbers).
- **Direction Arrow**: Scatter or deviation direction (N, NE, E, SE, S, SW, W, NW).
