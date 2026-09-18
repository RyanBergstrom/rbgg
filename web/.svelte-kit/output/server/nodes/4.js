import * as universal from '../entries/pages/games/_gameId_/setup/_page.js';

export const index = 4;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/games/_gameId_/setup/_page.svelte.js')).default;
export { universal };
export const universal_id = "src/routes/games/[gameId]/setup/+page.js";
export const imports = ["_app/immutable/nodes/4.CraVZ-ky.js","_app/immutable/chunks/D84Y2HP9.js","_app/immutable/chunks/D6YF6ztN.js","_app/immutable/chunks/DZt3FjrX.js","_app/immutable/chunks/B8oN67lD.js"];
export const stylesheets = ["_app/immutable/assets/4.DOwVh56U.css"];
export const fonts = [];
