# FOF Frontend Unslop Plan

Apply the Unslop design pass to the Fields of Fire frontend only. Gameplay, state, legal-move handling, and backend APIs stay unchanged; only presentation, copy, spacing, color, type, details, and motion change.

## Context

Current FOF UI lives in:

- `web/src/routes/games/[gameId]/play/+page.svelte`
- `web/src/lib/components/GameProgressPanel.svelte`
- `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte`
- `web/src/lib/components/games/fields_of_fire/TurnSequenceTracker.svelte`
- `web/src/lib/components/games/fields_of_fire/CommandPanel.svelte`
- `web/src/lib/styles/game-utils.css`

Current tells: overused gold (`#ffd700`), colored glows on legal/placing/focused cards, uppercase tracked labels, arbitrary radii and spacing, default font, hover transforms, and a light footer under a dark board.

## Direction

- **Product.** A solitaire tactical wargame where the player commands a US infantry company through terrain cards, counters, command activations, and a strict turn sequence.
- **Character.** Field-worn, methodical, quiet. Measured like a sand table, not a dashboard.
- **World.** Topographic map at dusk: olive, khaki, slate, muted brass. Color stays in the map and counters; chrome stays neutral.
- **Moments.** (1) Terrain map and stacked counters. (2) Command activation strip and pool counts. (3) Turn sequence as quiet navigation.
- **Signature.** Monospace card/counter indices and small readiness dots; no gold glow.

## Audit

- Gold accent is the default for legal moves, counts, popups, and collapse buttons in `FieldsOfFireBoard.svelte`, `CommandPanel.svelte`, and `TurnSequenceTracker.svelte`.
- Colored glows: `.has-legal-moves`, `.placing-target`, `.stack-focused`, `.dp-hover-preview` in `FieldsOfFireBoard.svelte`.
- Uppercase tracked labels: `.cp-hq small` in `CommandPanel.svelte`; `PLACE HERE` badge in `FieldsOfFireBoard.svelte`.
- Arbitrary spacing/radii across all four FOF components.
- Hover movement: `.game-card.playable:hover`, `.game-slot.legal-destination:hover`, `.game-slot.legal-draw:hover` in `game-utils.css`.
- Exclamation mark in winner banner: `Mission complete - {winner} wins!`.
- No visible focus rings on most controls.
- Small text below 11px in several places.
- Footer is light gray under a dark olive board in FOF mode.

## Implementation

### 1. Tokens

Create `web/src/lib/styles/fof-theme.css` and import it in `web/src/routes/+layout.svelte`.

Use `--fof-*` variables:

- Surfaces: `--fof-bg`, `--fof-surface`, `--fof-surface-2`, `--fof-surface-3`
- Lines/text: `--fof-border`, `--fof-border-strong`, `--fof-text`, `--fof-text-2`, `--fof-muted`
- Accent: `--fof-accent` (muted brass), `--fof-accent-text` (dark)
- Semantics: `--fof-danger`, `--fof-success`, `--fof-warning`
- Radius: `--fof-radius-sm` (6), `--fof-radius-md` (10), `--fof-radius-lg` (14)
- Space: 4, 8, 12, 16, 20, 24, 32
- Type: `--fof-font`, `--fof-mono`
- Motion: `--fof-ease`, `--fof-dur-fast` (120ms), `--fof-dur-base` (200ms)

Optional font import: IBM Plex Sans + IBM Plex Mono. If network fonts are not approved, use `system-ui` and `ui-monospace`.

### 2. Spacing and radius pass

- Replace arbitrary `rem`/`px` values with the 4px scale.
- Panel padding: 12-16. Card radius: 8. Controls: 6. Popups: 10.
- Sidebar width: 240. Map max width: 960.
- Nested radii must add up: inner radius = outer radius - padding, minimum 4.

### 3. Color pass

- Board background: `--fof-bg`.
- Panels/surfaces: `--fof-surface` / `--fof-surface-2`.
- Borders: `--fof-border`.
- Text roles: primary `--fof-text`, secondary `--fof-text-2`, muted `--fof-muted`.
- Accent only for primary action, selection, and key counts; use `--fof-accent` with `--fof-accent-text` on top.
- Remove glows, colored shadows, hue gradients, and gold box-shadows.
- Legal-move affordance: 2px `--fof-accent` outline, no glow.
- Placing/stack focus: 2px `--fof-accent` or `--fof-success` outline, no glow.
- Winner banner: surface + accent border, no brown fill.
- FOF-mode footer in `GameProgressPanel.svelte`: dark surface, light text, toned buttons.

### 4. Icons and copy pass

- No emoji is present in FOF; keep glyphs only if needed and normalize size/color.
- Sentence case labels: `Cards remaining`, `Discard {count}`, `Place here`, `No activity yet`, `Activity log`.
- Remove exclamation mark: `Mission complete. {winner} wins.`
- CommandPanel small labels: `Ready`, `Finished`, `Draw`, `Available`; remove `text-transform: uppercase` and `letter-spacing`.
- `no VOF target` -> `No VOF target`.
- Optional phase display helper in `GameProgressPanel.svelte`: replace underscores and title-case phase names.

### 5. Type pass

- Use `--fof-font` for UI and `--fof-mono` for counts, card indices, audit times, rule text.
- Weights: 400 body, 500 labels, 600 rare emphasis.
- No 700-900 headings, no negative tracking on small text.
- Numbers use `font-variant-numeric: tabular-nums`.
- Small text minimum 11px (0.7rem).

### 6. Layout pass

- Keep desktop proportions: 240px left rail, fluid map capped at 960px.
- Compose the first screen as a whole; avoid dead empty bands.
- Mobile (`max-width: 640px`): stack sidebar above map, panels full width, map full width, popups full width with safe margins.
- Keep popups anchored and scrollable.

### 7. Details pass

- Counts/meta as mono muted text, not glowing pills.
- Progress bar: muted track, accent fill, 120ms width transition.
- Hover/focus: color/border change only, no transform.
- Visible focus ring on all buttons/controls.
- Nested radii add up.

### 8. Visuals pass

- No generated images for this app screen.
- Keep real counter images and terrain cards as the visual moment.
- Remove decorative fills that do not carry meaning.
- Keep the map grid as the primary visual; do not add blobs, orbs, or gradients.

### 9. Motion pass

- Remove hover transforms from `game-utils.css` or scope them out of FOF.
- Use named transitions only: `transition-colors`, `transition-[border-color,background-color,opacity]`.
- One easing curve and durations from tokens.
- One short entrance at most for main content if used.
- Respect `prefers-reduced-motion`.

## Files To Change

- `web/src/lib/styles/fof-theme.css` (new)
- `web/src/routes/+layout.svelte`
- `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte`
- `web/src/lib/components/games/fields_of_fire/TurnSequenceTracker.svelte`
- `web/src/lib/components/games/fields_of_fire/CommandPanel.svelte`
- `web/src/lib/components/GameProgressPanel.svelte`
- `web/src/lib/styles/game-utils.css`
- `web/src/routes/games/[gameId]/play/+page.svelte` (banner/copy only)

## Validation

- `cd web; npm run check`
- `cd web; npx vitest run tests/unit/play-page.test.ts`
- Browser check FOF at desktop and mobile widths:
  - setup, command, and combat phases
  - popups and stack hover
  - keyboard focus rings
  - no console errors
- Contrast check for accent text and small text.

## Risks

- Large scoped CSS edits can regress other games if tokens are not namespaced; keep all new variables under `--fof-*`.
- Dark footer changes must be scoped to `.fof-mode`.
- Font import may be undesirable; default to system fonts if not approved.

## Out Of Scope

- Backend or game rules.
- Other games.
- Story/video generation unless requested.
- New gameplay features.
