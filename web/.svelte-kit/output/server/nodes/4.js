import * as universal from '../entries/pages/games/_gameId_/play/_page.js';

export const index = 4;
let component_cache;
export const component = async () => component_cache ??= (await import('../entries/pages/games/_gameId_/play/_page.svelte.js')).default;
export { universal };
export const universal_id = "src/routes/games/[gameId]/play/+page.js";
export const imports = ["_app/immutable/nodes/4.D63JjDZV.js","_app/immutable/chunks/5JXyHpLP.js","_app/immutable/chunks/uBIymjUX.js","_app/immutable/chunks/xihTtKlq.js","_app/immutable/chunks/DVM-L3dX.js","_app/immutable/chunks/CoCz9SgO.js","_app/immutable/chunks/BkbXeqTE.js","_app/immutable/chunks/D6tC14LY.js","_app/immutable/chunks/Cak6kzeI.js","_app/immutable/chunks/BJiQFusM.js"];
export const stylesheets = ["_app/immutable/assets/4.B5OJmVdg.css","_app/immutable/assets/FieldsOfFireBoard.CDzXKk2c.css","_app/immutable/assets/BusBoard.DOlsHwg0.css","_app/immutable/assets/CheckersBoard.BstDjYec.css","_app/immutable/assets/LostCitiesBoard.CylaMi8S.css","_app/immutable/assets/TwilightStruggleBoard.VODqShwk.css"];
export const fonts = [];
