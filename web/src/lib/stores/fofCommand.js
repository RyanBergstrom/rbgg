import { writable, derived } from 'svelte/store';

export const fofCommand = writable(null);

// Movement action state for board-based selection
export const movementAction = writable({
  type: null,
  step: 'idle',
  selectedUnitId: null,
  originatorId: null,
});

// Debug: log all changes
movementAction.subscribe(value => {
  console.log('[movementAction] state changed:', JSON.stringify(value));
});

// Derived store for eligible pieces (computed on the board side via function)
export function computeEligibleMoveUnits(legalMoves, actionType, originatorId) {
  if (!legalMoves.length || !actionType) return new Set();
  
  const moves = legalMoves.filter(m => m.type === actionType && m.originator_hq_id === originatorId);
  
  if (actionType === 'move_to_an_adjacent_card') {
    return new Set(moves.map(m => m.unit_id));
  }
  
  if (actionType === 'move_a_platoon_to_an_adjacent_card') {
    return new Set(moves.map(m => m.unit_id));
  }
  
  return new Set();
}

export function computeValidDestinations(legalMoves, actionType, originatorId, unitId) {
  if (!legalMoves.length || !actionType || !unitId) return new Set();
  
  const moves = legalMoves.filter(m => 
    m.type === actionType && 
    m.originator_hq_id === originatorId && 
    m.unit_id === unitId
  );
  
  return new Set(moves.map(m => m.to_position));
}

export const eligibleMoveUnits = derived(
  [fofCommand, movementAction],
  ([$fofCommand, $movementAction]) => {
    if (!$fofCommand || !$movementAction.type) return new Set();
    return computeEligibleMoveUnits($fofCommand.legalMoves, $movementAction.type, $movementAction.originatorId);
  }
);

export const validMoveDestinations = derived(
  [fofCommand, movementAction],
  ([$fofCommand, $movementAction]) => {
    if (!$fofCommand || !$movementAction.type || !$movementAction.selectedUnitId) return new Set();
    return computeValidDestinations($fofCommand.legalMoves, $movementAction.type, $movementAction.originatorId, $movementAction.selectedUnitId);
  }
);