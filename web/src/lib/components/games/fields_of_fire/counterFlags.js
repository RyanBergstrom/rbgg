/** Derive display flags from canonical unit state. */
export function getCounterFlags(unit) {
  if (!unit || typeof unit !== 'object') return [];

  const flags = [];
  const status = String(unit.status || '').toLowerCase();
  const exposed = unit.exposed === true || status === 'exposed';

  if (exposed) {
    flags.push({ id: 'exposed', label: 'EXPOSED', tone: 'warn' });
  }
  if (status === 'pinned') {
    flags.push({ id: 'pinned', label: 'PINNED', tone: 'danger' });
  }
  if (unit.activated === true) {
    flags.push({ id: 'activated', label: 'ACTIVATED', tone: 'info' });
  }

  return flags;
}
