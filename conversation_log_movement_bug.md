# Conversation Log: Movement Bug Fix Attempt

## User's Original Issue (2026-11-27T05:59:25Z)
> there is an issue with the the Move to an adjacent car action. when I click 1st platoon, then i clikc move to an adjacent card everything works, it highlights eligible units i can click so i click one like 1/1 plt it puts a green bar arround the card i can move to whic is good. But thats it. I can't do anyhthing after this point. If i click on the car i want to move it it just adds a VOF to that card which whoudl not happen. I don't want terrain clicks to add VOF, the game shoudl calculate VOF on it's own so i want the move to complete

## Root Cause Identified
The `handleCardClick` function in `FieldsOfFireBoard.svelte` didn't handle the `select_destination` step of the movement action flow. When a unit was selected, the `movementAction` store changed to `step: 'select_destination'`, but clicking a card fell through to the generic `getLegalMoveForCard` which found VOF placement moves instead of completing the movement.

## Fix Applied (FieldsOfFireBoard.svelte)
Added handling for `select_destination` step in `handleCardClick`:

```javascript
// Movement action: select_destination step - complete the move
const $movementAction = $movementActionStore;
if ($movementAction.type && $movementAction.step === 'select_destination' && $movementAction.selectedUnitId) {
  const move = legalMoves.find(m => 
    m.type === $movementAction.type &&
    m.originator_hq_id === $movementAction.originatorId &&
    m.unit_id === $movementAction.selectedUnitId &&
    m.to_position === idx
  );
  if (move) {
    dispatch('select-move', move);
    movementActionStore.set({ type: null, step: 'idle', selectedUnitId: null, originatorId: null });
  }
  return;
}
```

## Subsequent Issues Discovered

### 1. CORS Errors Blocking Move Submission
After the movement flow worked on frontend, moves were blocked by CORS policy when sent to backend.

**Backend CORS Fixes Attempted:**
- Added `http://localhost:5174` to CORSMiddleware allow_origins
- Added custom CORSFixMiddleware
- Replaced FastAPI CORSMiddleware entirely with custom implementation handling:
  - Preflight OPTIONS requests
  - All responses including error responses
  - Access-Control-Allow-Credentials headers

### 2. JSON Parse Errors in Backend
Legal moves endpoint returning 422 due to JSON parsing issues with curl testing.

### 3. Frontend ReferenceError: currentPlayerId
```
ReferenceError: currentPlayerId is not defined
    at FieldsOfFireBoard.svelte:791:21
```

This appears to be a pre-existing bug in the component, not related to the movement fix.

## Files Modified
1. `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte` - Added select_destination handling
2. `api/app/__init__.py` - Complete CORS middleware rewrite
3. `web/src/lib/components/games/fields_of_fire/CommandPanel.svelte` - Removed unit/destination dropdowns from nav bar (earlier in session)

## Testing Results
- Frontend movement flow works: select commander → select "Move To An Adjacent Card" → click eligible unit (green highlight) → click destination card → `movementAction` resets to idle
- Move dispatch fires correctly (confirmed via console logging)
- CORS preflight works (200 OK with proper headers)
- POST requests now include CORS headers in responses
- Backend returns 422 validation error (expected for test payload) instead of CORS block

## Outstanding Issues
1. Frontend `currentPlayerId` ReferenceError needs investigation
2. Backend legal-moves endpoint JSON parsing needs verification
3. Full end-to-end move submission needs validation with real move payload

## Time Spent
~23 minutes from initial report to current state