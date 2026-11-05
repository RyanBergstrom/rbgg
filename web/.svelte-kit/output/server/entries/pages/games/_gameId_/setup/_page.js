//#region src/routes/games/[gameId]/setup/+page.js
function load({ params }) {
	return { gameId: params.gameId };
}
//#endregion
export { load };
