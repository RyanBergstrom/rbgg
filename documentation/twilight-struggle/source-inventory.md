# Twilight Struggle Source Inventory

**Status:** source inventory completed. User confirmed standard base-game scope, the supplied 2nd Edition PDF as primary rules source, and asset permission for this app. This is an inventory, not a rules specification.

## Supplied source bundle

| Source | Observed contents | Use / limitation |
|---|---|---|
| `TS_Rules_Deluxe.pdf` | 32-page Twilight Struggle 2nd Edition rulebook; cover identifies Deluxe Edition; copyright © 2007 GMT Games, LLC. Includes core rules, tournament/optional material, variants, Late War scenario, examples, and card histories. | User-confirmed primary rules source; record any external errata/ruling conflict before changing behavior. Avoid reproducing rulebook prose. |
| `The Complete Card List v1.4.pdf` | 48-page card-by-card reference. Selectable text includes card number, operations, associated side, and effect summaries; sections distinguish standard, optional, and promotional cards. PDF metadata credits Alexandre Fafard and dates creation to 2016-01-16. | Useful secondary reference for event-effect inventory; cross-check card identity and behavior with the supplied primary rulebook and card face. Filter strictly to standard base-game cards; do not treat expanded numbering as the base deck. |
| `buildFile.xml` | VASSAL module “Twilight Struggle 3.1”, described as “Deluxe Edition”, module version 3.2, built for VASSAL 3.6.16. References main board image `TS Map-11.jpg`; contains region coordinates, board zones/tracks, setup stacks, piece slots, card slots, draw piles, global properties, player hands, and compact VASSAL trait definitions. | Component/layout inventory and cross-checking aid; not a stand-alone rules engine. Custom `ca.mkiefte` module behavior and VASSAL trait encodings need independent interpretation. |
| `images/` | 208 assets: 193 SVG, 13 PNG, 2 JPG. Includes `TS Map-11.jpg`, `TS Box cover.jpg`, track/counter art, and 110 numbered `TNRnTS-*.svg` card-face assets. | User confirmed permission for use in this app; do not infer broader redistribution rights. |

## XML structural summary

A local XML parse succeeded: 976 elements, including 274 setup stacks, 287 piece slots, 110 card slots, 6 draw piles, 130 region definitions, 6 zones, and 21 global properties; 397 unique GPID values. These counts describe the VASSAL module and do not prove the official card inventory or rules coverage.

The region definitions include map-coordinate origins, while separate zones cover DEFCON, Military Operations, Round, Turn, Space Race, and Victory Points. Do not infer country adjacency, battleground status, control rules, or legal moves from visual proximity or artwork coordinates alone.

## Rulebook topics observed

The extracted text has substantive rules sections on components, setup, turn sequence, card play, operations, events, DEFCON and military operations, China, scoring and victory. It also contains tournament play, a Chinese Civil War variant, a Late War scenario, optional rules, an extended example, and card histories. The existence of a section does not establish that its feature is intended for the initial app scope or supported by the VASSAL module.

## Card reference PDF

`The Complete Card List v1.4.pdf` is a 48-page, selectable-text card reference. Inspection confirmed individual entries with card number, operations, side/alignment, and effect summaries. It includes standard cards as well as optional and promotional cards (including IDs beyond the VASSAL module's 1–110 range), so it must be filtered to the user-approved standard base-game scope. Use it to build a structured effect checklist, not as sole authority: verify each included entry against the 2nd Edition rulebook and supplied card-face asset, and record discrepancies rather than silently combining versions.

The user has since confirmed the cards in scope/reference using [card-reference-validation.csv](card-reference-validation.csv). Treat its validated entries as the confirmed card inventory for this implementation. Entries not validated are promotional cards not available for this implementation and are out of scope. CSV validation means the card reference was confirmed, not that its event is already implemented or tested.

## Authority and rights gaps

1. User confirmed the supplied PDF as primary; no separate errata/FAQ/rulings source has been identified.
2. User confirmed standard base game only; exclude tournament/optional rules, variants, and scenarios.
3. User confirmed asset permission for this app; preserve provenance and scope.
4. Independently verify the country graph, country attributes, setup, full card definitions/effects, and timing against the approved rules authority.

## Implementation implications

Twilight Struggle is a two-player, card-driven area-control game with hidden hands and stochastic deck order. A faithful implementation needs a structured country graph and card catalog, validator-owned action/turn/round progression, private hand serialization, event/operations resolution, scoring and terminal rules, and an interface for multi-step card effects. The VASSAL XML may help locate components, but its compact trait data should not be imported as authoritative application behavior. RL remains downstream of the complete human-playable gate.
