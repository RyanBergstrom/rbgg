

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export const imports = ["_app/immutable/nodes/0.dweZZ8vU.js","_app/immutable/chunks/D84Y2HP9.js","_app/immutable/chunks/DZt3FjrX.js"];
export const stylesheets = ["_app/immutable/assets/0.DtdvzrPm.css"];
export const fonts = [];
