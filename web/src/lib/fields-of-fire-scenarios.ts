import { API_BASE } from './api';

export async function fetchFoFScenarios() {
  const res = await fetch(${API_BASE}/games/fields_of_fire/scenarios);
  if (!res.ok) throw new Error('Failed to load scenarios');
  return res.json();
}

export function getScenarioImageUrl(cardId: string) {
  if (!cardId) return null;
  return ${API_BASE}/img/fof/.jpg;
}
