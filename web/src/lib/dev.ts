const DEV = import.meta.env.VITE_DEV === 'true';

function log(source: string, label: string, data?: unknown) {
  if (!DEV) return;
  const ts = new Date().toISOString().slice(11, 23);
  if (data !== undefined) {
    console.log(`[${ts}] [${source}] ${label}`, structuredClone(data));
  } else {
    console.log(`[${ts}] [${source}] ${label}`);
  }
}

export function traceApi(source: string, label: string, data?: unknown) {
  log(source, label, data);
}

export function traceState(source: string, label: string, data?: unknown) {
  log(source, label, data);
}

export function traceMove(source: string, label: string, data?: unknown) {
  log(source, label, data);
}

export function tracePhase(source: string, label: string, data?: unknown) {
  log(source, label, data);
}

export function traceRender(source: string, label: string, data?: unknown) {
  log(source, label, data);
}

export const IS_DEV = DEV;
