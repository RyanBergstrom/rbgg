# rbgg - Santorini Game

## Quick Start

### 1. Backend API (Python)

```bash
cd /dev/rbgg/api
pip install -e .[dev]
uvicorn app:app --reload
```

API runs at `http://127.0.0.1:8000/api`

### 2. Frontend (Svelte)

```bash
cd /dev/rbgg/web
npm install
npm run dev  # or: npx svdev
```

Frontend runs at `http://localhost:5173`

### 3. Run Tests

```bash
# Unit tests
cd /dev/rbgg/web
npx vitest run

# End-to-end tests
cd /dev/rbgg/api
pytest tests/test_santorini_end_to_end.py -v
```

### 4. Game Flow

1. Start the API server first
2. Start the frontend dev server  
3. Open `http://localhost:5173` with `?gameId=santorini` in URL
4. Player 1 (AI or human) makes moves
5. Player 2 (AI auto-turn enabled) makes moves
6. Game-over banner appears when win condition met

### Key Endpoints
- `GET /api/games/` - Create/get game
- `GET /api/games/{gameId}` - Get game state
- `GET /api/sessions?gameId={id}` - Get sessions
- `POST /api/moves/ai` - AI move endpoint
- `POST /api/moves/{gameId}` - Submit move
