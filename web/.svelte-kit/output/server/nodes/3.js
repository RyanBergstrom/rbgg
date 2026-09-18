import * as universal from '../entries/pages/games/_gameId_/play/_page.js';

export const index = 3;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/games/_gameId_/play/_page.svelte.js')).default;
export { universal };
export const universal_id = "src/routes/games/[gameId]/play/+page.js";
export const imports = ["_app/immutable/nodes/3.DcLiC6QI.js","_app/immutable/chunks/BA1STT3q.js","_app/immutable/chunks/C1FmrZbK.js","_app/immutable/chunks/D84Y2HP9.js","_app/immutable/chunks/DZt3FjrX.js","_app/immutable/chunks/B8oN67lD.js","_app/immutable/chunks/BAsstkaf.js"];
export const stylesheets = ["_app/immutable/assets/3.CkhBbzR_.css"];
export const fonts = [];
