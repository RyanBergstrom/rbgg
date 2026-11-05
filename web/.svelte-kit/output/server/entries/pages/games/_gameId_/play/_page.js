//#region src/routes/games/[gameId]/play/+page.js
function load({ params, url }) {
	return {
		gameId: params.gameId,
		debug: url.searchParams.get("d") === "true" || url.searchParams.get("d") === "1"
	};
}
//#endregion
export { load };
