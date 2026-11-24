

export const index = 0;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/_layout.svelte.js')).default;
export const imports = ["_app/immutable/nodes/0.D0aUMrMY.js","_app/immutable/chunks/Rr-Im1Oz.js","_app/immutable/chunks/xihTtKlq.js","_app/immutable/chunks/DRhpOcIC.js"];
export const stylesheets = ["_app/immutable/assets/0.52v5p-hL.css"];
export const fonts = [];
