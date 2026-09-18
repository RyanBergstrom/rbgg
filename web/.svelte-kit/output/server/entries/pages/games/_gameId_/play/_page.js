function load({ params, url }) {
  return {
    gameId: params.gameId,
    debug: url.searchParams.get("d") === "true" || url.searchParams.get("d") === "1"
  };
}
export {
  load
};
