# Adding a New Game — Step-by-Step Guide

> **Revision History**
> - **v1.2** (2026-09-11 PM) — Added click-to-select-card UX pattern, shared game-utils.css classes, current_player sync rules, phase fallback from game_data, image path conventions, serialization return format. Corrected Step 5 with new board interaction model. Added Gotchas for current_player/phase management.
> - **v1.1** (2026-09-11 AM) — Added lessons from Lost Cities implementation: multi-phase turns, card game patterns, image handling, scoring callbacks, AI move matching by content not ID, round transitions, discard pile draw restrictions. Added Step 3.5 for custom panels, expanded config reference for background_image components, added serialize.py patterns for non-grid games.
> - **v1.0** (2026-09-10) — Initial version based on Checkers implementation.

This guide walks an LLM agent through adding a new game to rbgg. It assumes the human user has already created a folder in `documentation/<game-name>/` containing game assets (rules, images, card data, etc.) and will point you to that folder.

---

## 1. Understand the Architecture

The rbgg framework separates **core infrastructure** (shared by all games) from **game-specific code** (validator, config, frontend board component).

| Layer                | Purpose                                                          | Files Games Touch                                             |
| -------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------- |
| **Config**           | YAML defines panels, components, rounds/turns/phases, difficulty | `configs/{game_id}.yaml`                                      |
| **Validator**        | Implements `LegalMoveValidator` — rules, moves, win check        | `api/app/games/{game_id}/validator.py`                        |
| **Serialize**        | Converts internal `game_data` → screen-ready dicts               | `api/app/games/{game_id}/serialize.py`                        |
| **Catalog/Registry** | Registers game + validator at startup                            | `api/app/__init__.py`                                         |
| **Frontend Board**   | Svelte component rendering the board, dispatching moves          | `web/src/lib/components/games/{game_id}/{GameId}Board.svelte` |
| **Tests**            | Backend validator tests + (optional) E2E                         | `api/tests/test_{game_id}.py`                                 |
| **Shared CSS**       | Reusable UI states (glow, selection, etc.)                       | `web/src/lib/styles/game-utils.css` (auto-loaded)             |

**Core files you generally do NOT modify:**

- `api/app/core/engine.py` — MovePipeline + GameEngine (generic)
- `api/app/core/config_loader.py` / `config_schema.py` — config parsing
- `api/app/core/game_state.py` — GameState envelope
- `api/app/core/legal_move_interface.py` — abstract validator interface
- `api/app/routes/*.py` — already game-agnostic
- `web/src/lib/styles/game-utils.css` — shared card/slot CSS states

---

## 2. Prerequisites (Human Preparation)

Before starting, the human should place these in `documentation/<game-name>/`:
Analyze the information provided by the human and use that to answer questions about this implementation

This could be rules, game component images, suggestions for layouts, configs etc.

All of it will be tied together with a single readme named <game-name>.md

---

## 3. Step-by-Step Implementation Order

### Step 1: Analyze Game Assets → Design Config

**Read** The game rules and look through any assets.

**Decide:**

- `game_id`: lowercase, no spaces (e.g., `checkers`, `chess`, `tic_tac_toe`)
- `game_type`: usually same as `game_id`
- `topology`: `grid` | `hex` | `graph` | `suggest other`
- Board dimensions (rows/columns)
- Panel layout: `game_progress` (required), `main_board` (required), plus any custom panels
- Component list for each panel: shapes, colors, grid mapping, stackable pieces, images for those pieces
- Round/Turn/Phase structure (see `checkers.yaml` for reference)
- Difficulty levels: MCTS iteration counts per level + `default`
- Min/max players

**Output:** Write `configs/{game_id}.yaml` to the api folder.

---

### Step 1.5: Plan Custom Panels (If Needed)

For games beyond simple grid boards, you may need additional panels:

- **Player hand panel** — for card games, shows player's private cards
- **Score panel** — running score display during play
- **Discard/draw piles** — separate visual zones with stackable components
- **Phase indicator** — shows current sub-phase (e.g., "Play a Card" vs "Draw a Card")

Define these in the config YAML under `panels:` with `required: false`. Each panel needs a unique `panel_id` and at least one component.

**Example for Lost Cities:**
```yaml
panels:
  game_progress:
    name: Game Progress
    required: true
  main_board:
    name: Main Board
    required: true
    components:
      # ... board, expeditions, discard piles, draw pile
  player_hand:
    name: Player Hand
    required: false
    components:
      hand_area:
        name: Hand Area
        shape: rectangle
        color: "#1a1a2e"
        z_index: 10
        grid:
          rows: 1
          columns: 10
        stackable: false
        clickable: true
```

---

### Step 2: Create Backend Validator

**File:** `api/app/games/{game_id}/validator.py`

**Inherit from:** `app.core.legal_move_interface.LegalMoveValidator`

**Implement all abstract methods:**

```python
class {GameName}Validator(LegalMoveValidator):
    def validate_move(self, state: dict, move: dict) -> bool:
        # Return True iff move is legal in state

    def get_legal_moves(self, state: dict, player_id: str) -> list[dict]:
        # Return ALL legal moves for player (complete move dicts)

    def apply_move(self, state: dict, move: dict) -> dict:
        # Return NEW state dict with updated game_data
        # Must include: {"game_data": {...}}

    def check_win(self, state: dict) -> str | None:
        # Return winner player_id or None
```

**Implement optional hooks:**

- `initial_game_data(self) -> dict` — starting board/pieces
- `serialize_for_screen(self, game_data) -> dict` — return serialized game data for screen
- `ai_config(self) -> MCTSConfig | None` — enable MCTS AI (return None for simple heuristic)
- `recommend_ai_move(self, state, candidates)` — fallback AI if no MCTS

**Move dict convention (used by frontend + engine):**

```python
{
    "move_id": "unique_string",
    "type": "move" | "jump" | "place" | "play_card" | "play_expedition" | "discard" | "draw" | ...,
    "from_row": int, "from_col": int,   # for grid moves
    "to_row": int, "to_col": int,
    "player_id": "player_1" | "player_2" | ...,
    # game-specific fields OK (e.g., "card", "color", "hand_index", "source", "over_row", "promotion")
}
```

**State dict passed to validator methods:**

```python
{
    "game_data": {...},           # your internal representation
    "players": [{"player_id": "...", "name": "...", "score": 0, "color": "#..."}, ...],
    "current_player_index": 0,    # engine tracks this; your game_data should keep it in sync
    "version": int,               # incremented by engine
}
```

**CRITICAL: Managing current_player**

The engine has its own `current_player_index` in `GameState`. Your game also has `game_data["current_player"]`. These MUST stay in sync. The engine automatically syncs `state.current_player_index` from `game_data["current_player"]` after every `apply_move` call. So:

- In `apply_move`, set `game_data["current_player"]` to the next player
- The engine will automatically update `state.current_player_index` to match
- In `get_legal_moves`, compare `game_data["current_player"]` with the `player_id` parameter — if they don't match, return `[]`

```python
def get_legal_moves(self, state, player_id):
    game_data = state.get("game_data", {})
    if game_data.get("current_player") != player_id:
        return []
    # ... return phase-appropriate moves
```

**CRITICAL: Managing phases**

The engine has its own round/turn/phase tracking. Your game also has `game_data["current_phase"]`. For games with custom phase management (like multi-phase turns):

- Store `current_phase` as a string in `game_data` (e.g., `"play_a_card"`, `"draw_a_card"`)
- Set `current_phase` to match a phase `name` from your YAML config's `rounds[].turns[].phases[]`
- The engine's `get_phase_info()` will automatically look up the phase name/text from config when `state.current_phase_index` doesn't match
- In `get_legal_moves`, switch on `game_data["current_phase"]` to return phase-appropriate moves

```python
def get_legal_moves(self, state, player_id):
    game_data = state.get("game_data", {})
    current_phase = game_data.get("current_phase")

    if current_phase == "play_a_card":
        return _get_legal_plays(state, player_id)
    elif current_phase == "draw_a_card":
        return _get_legal_draws(state, player_id)
    return []
```

**Multi-phase turn handling in apply_move:**

```python
def apply_move(self, state, move):
    game_data = deepcopy(state.get("game_data", {}))
    move_type = move.get("type")

    if move_type == "play_expedition" or move_type == "discard":
        game_data["current_phase"] = "draw_a_card"
        game_data["pending_draw"] = True
    elif move_type == "draw":
        game_data["current_phase"] = "play_a_card"
        game_data["current_player"] = _opponent(player_id)
        game_data["pending_draw"] = False

    return {"game_data": game_data}
```

**Move validation by content, not ID:**

The `move_id` is generated by `get_legal_moves` and may differ from what the frontend sends. Match moves by their semantic content:

```python
def validate_move(self, state, move):
    legal_moves = self.get_legal_moves(state, move["player_id"])
    for legal in legal_moves:
        if (legal["type"] == move["type"] and
            legal.get("card") == move.get("card") and
            legal.get("color") == move.get("color") and
            legal.get("source") == move.get("source")):
            return True
    return False
```

---

### Step 3: Create Serialization Helpers

**File:** `api/app/games/{game_id}/serialize.py`

**CRITICAL: Return format**

`serialize_for_screen()` must return a dict that the frontend can consume directly. For card games, this means serialized objects (not raw card strings):

```python
def serialize_for_screen(self, game_data):
    return {
        "player_hands": {pid: serialize_hand(h, ...) for pid, h in game_data["player_hands"].items()},
        "expeditions": {pid: {c: serialize_expedition(...) for c in COLORS} for pid in [...]},
        "discard_piles": {c: serialize_discard_pile(...) for c in COLORS},
        "draw_pile": {"count": len(draw_pile), "image": card_back_path()},
        "current_phase": game_data["current_phase"],
        "current_player": game_data["current_player"],
        "scores": game_data["scores"],
        "round": game_data["round"],
        "game_over": game_data["game_over"],
    }
```

**Image path convention:**

All image paths returned by the serializer must be absolute from the web root:

```python
def card_image_path(card: str) -> str:
    color_short = card.split("_")[0]
    num = card.split("_")[1]
    return f"/api/v1/img/{game_id}/cards/{color_short}_{num}.jpg"

def card_back_path() -> str:
    return f"/api/v1/img/{game_id}/cards/card_backs.jpg"
```

The static files are served at `/api/v1/img/` via `StaticFiles` mount in `api/app/__init__.py`. Never use relative paths like `api/img/...`.

**Typical serialization functions for card games:**

```python
def serialize_hand(hand, is_current_player, is_ai=False):
    """Show card faces for human player, backs for AI."""
    result = []
    for idx, card in enumerate(hand):
        if is_current_player and not is_ai:
            result.append({
                "id": f"hand_{idx}",
                "card": card,
                "image": card_image_path(card),
                "color": card.split("_")[0],
                "value": card.split("_")[1],
                "face_up": True,
            })
        else:
            result.append({
                "id": f"hand_{idx}",
                "card": card,
                "image": card_back_path(),
                "face_up": False,
            })
    return result

def serialize_expedition(cards):
    """Serialize played cards in an expedition."""
    return [{"id": f"exp_{i}", "card": c, "image": card_image_path(c)}
            for i, c in enumerate(cards)]

def serialize_discard_pile(cards):
    """Only top card fully visible."""
    if not cards:
        return {"cards": [], "top_card": None, "count": 0}
    top = cards[-1]
    return {
        "cards": cards,
        "top_card": {"card": top, "image": card_image_path(top)},
        "count": len(cards),
    }
```

**For grid-based games (Checkers, Chess):**

Create `board_to_cells()` that converts your board array to the cells format:

```python
def board_to_cells(board) -> list[list[dict]]:
    """Convert board array to screen-ready cells."""
    return [
        [{"color": "#hex", "piece": {...} | None} for col in row]
        for row in board
    ]
```

---

### Step 3.5: Create Frontend Board Component (Card/Non-Grid Games)

**File:** `web/src/lib/components/games/{game_id}/{GameId}Board.svelte`

**Props (all optional, passed by play page):**

```svelte
<script>
  export let game = null;
  export let gameId = '{game_id}';
  export let legalMoves = [];
  export let screenState = null;
  export let pendingMove = null;
</script>
```

**CRITICAL: Click-to-Select UX Pattern**

Do NOT use Play/Discard/Move buttons. Use a click-to-select flow:

1. Player clicks a card/piece in their hand/board → it becomes "selected" (lifts up, green glow)
2. Legal destinations highlight (green glow for play targets, blue glow for draw sources)
3. Player clicks a legal destination → move executes
4. Player can click the same card again to deselect

This pattern uses shared CSS classes from `game-utils.css` (auto-loaded via `+layout.svelte`):

| Class | Element | Effect |
|-------|---------|--------|
| `game-card` | Hand cards, playable pieces | Base class for card states |
| `game-card.playable` | Cards with legal moves | Gold border, lift on hover |
| `game-card.selected` | Currently selected card | Green border + lift + glow |
| `game-slot` | Expedition slots, discard piles, draw pile | Base class for slot states |
| `game-slot.legal-destination` | Slots where selected card can go | Green glow + scale on hover |
| `game-slot.legal-draw` | Piles the player can draw from | Blue glow + scale on hover |

**Template pattern for click-to-select:**

```svelte
<div class="hand-cards">
  {#each hand as cardObj, idx}
    <div
      class="hand-card game-card"
      class:playable={isPlayPhase && hasLegalMove(cardObj)}
      class:selected={selectedHandIndex === idx}
      on:click={() => handleCardClick(cardObj, idx)}
    >
      <CardImage src={cardObj.image} alt={cardObj.card} />
    </div>
  {/each}
</div>

<!-- Destinations -->
<div
  class="card-slot expedition-slot game-slot"
  class:legal-destination={canPlayToExpedition(color)}
  on:click={() => handleExpeditionClick(color)}
>
  ...
</div>
```

**Script pattern for click-to-select:**

```svelte
<script>
  let selectedCard = null;
  let selectedHandIndex = null;

  function handleCardClick(cardObj, idx) {
    if (isBoardLocked || isDrawPhase) return;
    if (selectedHandIndex === idx) {
      clearSelection();
      return;
    }
    selectedCard = cardObj;
    selectedHandIndex = idx;
  }

  function canPlayToExpedition(color) {
    if (!selectedCard || !isPlayPhase) return false;
    return legalMoves.some(m =>
      m.type === 'play_expedition' &&
      m.card === selectedCard.card &&
      m.color === color
    );
  }

  function handleExpeditionClick(color) {
    if (!isPlayPhase || !selectedCard) return;
    const move = legalMoves.find(m =>
      m.type === 'play_expedition' &&
      m.card === selectedCard.card &&
      m.color === color
    );
    if (move) {
      clearSelection();
      dispatch('select-move', move);
    }
  }

  function clearSelection() {
    selectedCard = null;
    selectedHandIndex = null;
  }
</script>
```

**Key board responsibilities:**

1. Read game data from `screenState.game_data`
2. Derive `isPlayPhase` / `isDrawPhase` from `game_data.current_phase`
3. Lock board when `winner` or `currentPlayerId !== 'player_1'` or `pendingMove`
4. Dispatch `select-move` events with the legal move object
5. Show phase-specific instructions in the hand label

---

### Step 4: Register Game + Validator

**File:** `api/app/__init__.py` (append at bottom)

```python
from app.games.catalog import register_game
from app.games.registry import register_validator
from app.games.{game_id}.validator import {GameName}Validator
from app.core.config_loader import load_game_config

_{game_id}_config = load_game_config("{game_id}")
_cover = _{game_id}_config.cover_image
if _cover and "/" in _cover:
    _cover = _cover.rsplit("/", 1)[-1]
register_game(
    "{game_id}",
    "Display Name",
    "{game_id}",
    min_players=_{game_id}_config.min_players,
    max_players=_{game_id}_config.max_players,
    cover_image=_cover,
    difficulty=_{game_id}_config.difficulty.to_dict() if _{game_id}_config.difficulty else None,
)
register_validator("{game_id}", {GameName}Validator())
```

---

### Step 5: Write Backend Tests

**File:** `api/tests/test_{game_id}.py`

**Test categories (mirror checkers):**

1. Initial board setup (piece counts, positions)
2. Simple moves (legal + illegal directions, blocked)
3. Jumps/captures (if applicable)
4. Mandatory capture rules
5. Promotion/special moves
6. `get_legal_moves` returns correct sets (jumps-only when jumps exist)
7. Win detection (no pieces, no moves)
8. AI heuristic / MCTS config
9. Serialization round-trip

**Card game specific test categories:**

1. Deck creation (correct card count, distribution)
2. Card parsing utilities (color, value, investment detection)
3. Expedition play legality (empty, investment-first, ascending order)
4. Discard rules (always legal, updates discard pile)
5. Draw phase (draw pile, discard piles, cannot draw own discard)
6. Scoring (empty, investment-only, numbered, multipliers, length bonus)
7. Round transition (draw pile exhausted → score → new round)
8. Multi-round game (3 rounds, cumulative score, winner)

**Fixture pattern:**

```python
@pytest.fixture
def validator():
    return {GameName}Validator()

def _make_state(board=None, current_player_index=0, players=None):
    if board is None:
        board = initial_board()
    if players is None:
        players = [{"player_id": "player_1", ...}, {"player_id": "player_2", ...}]
    return {
        "game_data": {"board": board, "current_player": "player_1", "current_phase": "..."},
        "current_player_index": current_player_index,
        "players": players,
    }
```

---

### Step 6: Run Backend Tests

```bash
cd api
pip install -e .[dev]
pytest tests/test_{game_id}.py -v
# Should pass all tests
pytest tests/ -v --ignore=tests/test_scaffold.py
# All tests should pass
```

---

### Step 7: Verify Frontend Integration

1. Start API: `cd api && python -m uvicorn app:app --reload`
2. Start frontend: `cd web && npm run dev`
3. Navigate to `http://localhost:5173/games/{game_id}/setup`
4. Verify:
   - Cover image loads
   - Difficulty dropdown shows config levels, defaults to `default` key
   - New Game form works (player name, min/max players from config)
   - Start Game → redirects to `/games/{game_id}/play`
   - Board component loads (dynamic import by `game.type`)
   - Click card → destinations highlight → click destination → move executes
   - AI moves work (if `ai_config` returns MCTSConfig)
   - Win detection shows winner banner

---

### Step 8: (Optional) Add E2E Test

**File:** `api/tests/test_{game_id}_end_to_end.py` (like `test_santorini_end_to_end.py`)

Uses Playwright to drive browser through full game.

---

## 4. Config YAML Reference

Minimal required structure (`configs/{game_id}.yaml`):

```yaml
game_id: {game_id}
name: "Display Name"
type: {game_id}
cover-image: api/img/{game_id}/cover.webp

difficulty:
  easy: 50
  medium: 300
  hard: 1500
  expert: 5000
  default: medium

panels:
  game_progress:
    name: Game Progress
    required: true
  main_board:
    name: Main Board
    required: true
    components:
      board:
        name: Board
        shape: rectangle
        color: "#hex"
        z_index: 0
        clickable: false
        grid:
          rows: 8
          columns: 8
      player1_pieces:
        name: Player 1 Pieces
        shape: circle
        color: "#hex"
        z_index: 10
        stackable: true
        stack_name: "p1_pool"
      player2_pieces:
        name: Player 2 Pieces
        shape: circle
        color: "#hex"
        z_index: 10
        stackable: true
        stack_name: "p2_pool"

rounds:
  - name: Main Game
    turns:
      - name: Player Turn
        phases:
          - name: Player_Turn
            text: "Make your move"
            order: 1
            confirm:
              required: false
          - name: Pass_Turn
            text: "Confirm your move"
            order: 2
            confirm:
              name: "Confirm"
              description: "End your turn"
              required: true
```

**Required panels:** `game_progress` and `main_board` (enforced by `GameConfig.__post_init__`).

**Component properties:**

- `shape`: `rectangle` | `circle` | `hex` | `diamond`
- `color` OR `background_image` (not both)
  - Use `color: "#hex"` for solid colored pieces/boards
  - Use `background_image: "api/img/{game_id}/cards/card_name.jpg"` for card faces, card backs, board art
  - Path is relative to API static mount at `/api/v1/img/`
- `grid`: `{rows, columns}` — defines cell coordinates for legal moves
- `stackable: true` + `stack_name` — for piece pools (multiple pieces in same visual slot)
- `clickable: false` — for static board background
- `z_index` — layer ordering (higher = on top)
- `hover_text` — tooltip on hover
- `rotate` — rotation in degrees (for hexagonal, etc.)

**Phase names must match between YAML and game_data:**

The `phase.name` in your YAML config must exactly match the `game_data["current_phase"]` string you set in `apply_move`. The engine looks up phase info by name when building screen state.

```yaml
rounds:
  - name: Main Game
    turns:
      - name: Player Turn
        phases:
          - name: play_a_card          # ← must match game_data["current_phase"]
            text: "Play a Card"        # ← shown in GameProgressPanel
            order: 1
            confirm:
              required: false
          - name: draw_a_card          # ← must match game_data["current_phase"]
            text: "Draw a Card"
            order: 2
            confirm:
              required: true
              name: "Confirm"
              description: "End your turn"
```

**Card game component patterns:**

```yaml
# Expedition slot with base image + stackable cards
p1_blue_exp:
  name: "P1 Blue Expedition"
  shape: rectangle
  background_image: "api/img/lost_cities/cards/b_base.jpg"
  z_index: 5
  grid:
    rows: 1
    columns: 1
  stackable: true
  stack_name: "p1_blue_exp"
  clickable: false

# Discard pile - clickable for drawing
blue_discard:
  name: "Blue Discard Pile"
  shape: rectangle
  background_image: "api/img/lost_cities/cards/card_backs.jpg"
  z_index: 5
  grid:
    rows: 1
    columns: 1
  stackable: true
  stack_name: "blue_discard"
  clickable: true
  hover_text: "Blue discard pile"

# Draw pile
draw_pile:
  name: "Draw Pile"
  shape: rectangle
  background_image: "api/img/lost_cities/cards/card_backs.jpg"
  z_index: 5
  grid:
    rows: 1
    columns: 1
  stackable: true
  stack_name: "draw_pile"
  clickable: true

# Player hand area
hand_area:
  name: Hand Area
  shape: rectangle
  color: "#1a1a2e"
  z_index: 10
  grid:
    rows: 1
    columns: 10
  stackable: false
  clickable: true
```

---

## 5. Common Gotchas

| Issue                                     | Solution                                                                                                                        |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `default` not appearing in API difficulty | Ensure `DifficultyConfig.to_dict()` includes `"default": self.default` (fixed in config_schema.py)                              |
| Frontend dropdown shows "Default"         | Setup page must filter `key !== 'default'` and set `selectedDifficulty = game.difficulty.default`                               |
| Board component not loading               | Play page does dynamic import: `import(\`$lib/components/games/${type}/${type}Board.svelte\`)` — file must match exactly        |
| Moves not validating                      | `validator.validate_move` receives state dict with `game_data`, `players`, `current_player_index` — not full GameState          |
| Multi-jump not working                    | `apply_move` must set `game_data.must_jump_from = {row, col}` when more jumps available; `get_legal_moves` must check this flag |
| AI not using difficulty                   | `moves.py` reads `state.difficulty` and overrides `MCTSConfig.iterations` from `game_config.difficulty.levels[difficulty]`      |
| `test_scaffold.py` failures               | Known pytest collection issue with editable install — ignore, not related to your game                                          |
| Move ID mismatch in validation            | Frontend sends move without `move_id` or different ID — match by semantic content (type, card, color, source) not `move_id`     |
| Multi-phase turn not working              | Store `current_phase` in `game_data`; set it to match a phase `name` in YAML config; check it in `get_legal_moves`              |
| Can't draw own discarded card             | Track `last_discarded` in `game_data`; filter it out in `get_legal_draws` for that player                                      |
| Images not loading in frontend            | Ensure images copied to `api/img/{game_id}/cards/`; use paths like `/api/v1/img/{game_id}/cards/xyz.jpg` (absolute from root)   |
| Svelte `{/each}` parse error              | Each `{#if}` must have matching `{/if}`; each `{#each}` must have matching `{/each}` — don't nest `{/each}` inside `{/if}` incorrectly |
| Scores not updating between rounds        | In `apply_move` when draw pile empty: calculate scores, increment round, call `_start_new_round()` which creates new deck       |
| Serializer KeyError on card colors        | Card strings use short codes (`b_5`, `r_i`); map via `COLOR_SHORT = {"blue": "b", ...}` and `SHORT_TO_COLOR` reverse map      |
| current_player out of sync                | Set `game_data["current_player"]` in `apply_move`; engine auto-syncs `state.current_player_index` — never set `current_player_index` directly |
| Phase text not showing in progress panel  | `game_data["current_phase"]` must match a `phase.name` in YAML config; engine looks up `phase.text` by name                     |
| Legal moves always empty                  | Check `get_legal_moves` compares `game_data["current_player"]` with `player_id` param — mismatch = return []                    |
| Click-to-select not working               | Add `game-card` / `game-slot` CSS classes to elements; toggle `playable`, `selected`, `legal-destination`, `legal-draw`          |

---

## 6. File Checklist for New Game

```
api/
├── configs/
│   └── {game_id}.yaml                    # ← CREATE
├── app/games/
│   └── {game_id}/
│       ├── __init__.py                   # ← CREATE (empty)
│       ├── validator.py                  # ← CREATE
│       └── serialize.py                  # ← CREATE
├── tests/
│   └── test_{game_id}.py                 # ← CREATE
├── app/__init__.py                       # ← EDIT (register game + validator)

web/
└── src/lib/components/games/{game_id}/
    └── {GameId}Board.svelte              # ← CREATE
```

**Image assets:**
```
api/img/{game_id}/
├── cover.webp                            # Game cover for catalog
└── cards/                                # Card images (for card games)
    ├── {color}_base.jpg                  # Expedition/base background
    ├── {color}_i.jpg                     # Investment cards
    ├── {color}_2.jpg through {color}_10.jpg
    └── card_backs.jpg                    # Card back
```

**Shared CSS (auto-loaded, no action needed):**
```
web/src/lib/styles/game-utils.css         # Already exists — provides game-card/game-slot states
```

---

## 7. Quick Reference — Validator Method Signatures

```python
# From legal_move_interface.py
class LegalMoveValidator(ABC):
    @abstractmethod
    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool: ...

    @abstractmethod
    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def check_win(self, state: dict[str, Any]) -> str | None: ...

    def recommend_ai_move(self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]) -> dict[str, Any] | None: ...

    def ai_config(self) -> "MCTSConfig | None": ...

    def initial_game_data(self) -> dict[str, Any]: ...

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]: ...
```

---

## 8. Debugging Tips

- **Backend:** Use `debug-load` endpoint to inject board state:
  ```bash
  curl -X POST http://localhost:8000/api/v1/moves/debug-load/{game_id} \
    -H "Content-Type: application/json" \
    -d '{"game_data": {"board": [...], "current_player": "player_1", "current_phase": "..."}, "current_player_index": 0}'
  ```
- **Frontend:** Enable `VITE_DEV=true` for trace logs; open DebugPanel on play page (`?debug=true`)
- **Legal moves:** Call `GET /api/v1/moves/legal-moves` with `{"game_id": "..."}` to see move list
- **Screen state:** `GET /api/v1/games/{game_id}` returns full `screen_state` with panels, phase, legal_moves
- **Phase info:** Check `screen_state.phase` — if empty, your `game_data["current_phase"]` doesn't match any phase name in YAML config

---

## 9. Example: Minimal Game (Tic-Tac-Toe)

For a simple game, the validator can be ~100 lines. Key simplifications:

- No MCTS needed → `ai_config()` returns `None`, `recommend_ai_move` picks first move
- No multi-jump → `apply_move` just places piece, toggles turn
- Win check → scan rows/cols/diagonals
- `serialize_for_screen` → convert 3x3 array to cells

---

## 10. Example: Card Game (Lost Cities Pattern)

For a 2-player card game with expeditions, discard piles, and multi-phase turns:

**Key structures:**
- `game_data` contains: `player_hands`, `expeditions`, `discard_piles`, `draw_pile`, `current_phase`, `current_player`, `scores`, `round`, `game_over`
- Two phases per turn: `play_a_card` → `draw_a_card`
- Cards encoded as strings: `"b_5"` (blue 5), `"r_i"` (red investment)
- Scoring: sum numbered cards - 20, x (1 + investments), +20 if 8+ cards

**Validator highlights:**
- `_can_play_to_expedition(exp, card)` — enforces investment-first, ascending order
- `_get_legal_plays()` — returns expedition plays + discards for each card in hand
- `_get_legal_draws()` — draw pile + discard tops (excluding own last discard)
- `apply_move()` — transitions phase, handles round end when draw pile empty
- `check_win()` — returns winner when `game_over` after 3 rounds
- `ai_config()` — returns `MCTSConfig(iterations=300, max_depth=40)`

**Serialization:**
- `serialize_hand()` — shows faces for human, backs for AI
- `serialize_expedition()` — shows all played cards with images
- `serialize_discard_pile()` — only top card fully visible
- `serialize_game_data()` — assembles everything for screen state
- All image paths use `/api/v1/img/lost_cities/cards/...` (absolute)

**Frontend board:**
- Three rows: AI expeditions (top), discard/draw piles (middle), player expeditions (bottom)
- Hand area at bottom with click-to-select cards
- Phase indicator shows "Play a card" or "Draw a card" from config
- Click card → legal destinations glow green → click destination → move executes
- Draw phase: draw pile and legal discard piles glow blue → click to draw

**Config highlights:**
- Custom `player_hand` panel (required: false)
- Components use `background_image` for card faces/backs
- `stackable: true` with `stack_name` for expedition slots and discard piles
- Multi-phase turn with confirm only on draw phase
- Phase names (`play_a_card`, `draw_a_card`) must match `game_data["current_phase"]`

---

## 11. Validation Before Handoff

Before marking the work item done, verify:

1. `pytest tests/test_{game_id}.py -v` — all pass
2. `pytest tests/ -v --ignore=tests/test_scaffold.py` — no regressions
3. `cd web && npm run build` — compiles without errors
4. Manual browser test: setup → play → click card → click destination → AI moves → win detection
5. No `TBD`/`TODO`/`FIXME` in new config or validator
6. `game_data["current_player"]` is set correctly in all `apply_move` code paths
7. `game_data["current_phase"]` matches a phase `name` in YAML config
8. Image paths start with `/api/v1/img/` (absolute, not relative)

---

_This guide covers the standard path. Each game will have unique rules requiring validator creativity — but the file structure, registration, and integration points remain the same._
