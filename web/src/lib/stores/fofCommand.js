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

const PLATOON_ACTIONS = new Set([
  'move_a_platoon_to_an_adjacent_card',
  'attempt_to_have_a_platoon_infiltrate_an_adjacent_card',
]);

const INFILTRATE_ACTIONS = new Set([
  'attempt_to_infiltrate_an_adjacent_card',
  'attempt_to_have_a_platoon_infiltrate_an_adjacent_card',
  'attempt_to_infiltrate_within_a_card',
]);

const UNIT_SELECTING_ACTIONS = new Set([
  'move_to_an_adjacent_card',
  'attempt_to_seek_cover',
  ...INFILTRATE_ACTIONS,
]);

// Derived store for eligible pieces (computed on the board side via function)
export function computeEligibleMoveUnits(legalMoves, actionType, originatorId) {
  if (!legalMoves.length || !actionType) return new Set();

  const moves = legalMoves.filter(m => m.type === actionType && m.originator_hq_id === originatorId);
  if (!UNIT_SELECTING_ACTIONS.has(actionType)) return new Set();
  return new Set(moves.map(m => m.unit_id));
}

export function computeValidDestinations(legalMoves, actionType, originatorId, unitId) {
  if (!legalMoves.length || !actionType) return new Set();

  const moves = legalMoves.filter(m =>
    m.type === actionType &&
    m.originator_hq_id === originatorId
  );

  // Platoon actions are one action for the whole platoon, so the destination is
  // chosen directly without selecting an individual counter first.
  if (PLATOON_ACTIONS.has(actionType)) {
    return new Set(moves.map(m => m.to_position));
  }

  if (!unitId) return new Set();
  return new Set(moves.filter(m => m.unit_id === unitId).map(m => m.to_position));
}

export const eligibleMoveUnits = derived(
  [fofCommand, movementAction],
  ([$fofCommand, $movementAction]) => {
    if (!$fofCommand || !$movementAction.type) return new Set();
    if (PLATOON_ACTIONS.has($movementAction.type)) return new Set();
    return computeEligibleMoveUnits($fofCommand.legalMoves, $movementAction.type, $movementAction.originatorId);
  }
);

export const validMoveDestinations = derived(
  [fofCommand, movementAction],
  ([$fofCommand, $movementAction]) => {
    if (!$fofCommand || !$movementAction.type) return new Set();
    if (
      !PLATOON_ACTIONS.has($movementAction.type) &&
      !$movementAction.selectedUnitId
    ) return new Set();
    return computeValidDestinations($fofCommand.legalMoves, $movementAction.type, $movementAction.originatorId, $movementAction.selectedUnitId);
  }
);
