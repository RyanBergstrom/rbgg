import "../../chunks/index-server.js";
import { T as escape_html, a as ensure_array_like, u as stringify, w as attr } from "../../chunks/server.js";
import "../../chunks/api.js";
//#region src/routes/+page.svelte
function _page($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		const API_BASE = "http://127.0.0.1:8000/api/v1";
		let games = [];
		function getCoverUrl(game) {
			if (!game.cover_image) return null;
			return `${API_BASE}/img/${game.cover_image}`;
		}
		$$renderer.push(`<main class="svelte-1uha8ag">`);
		if (games.length === 0) $$renderer.push(`<!--[1--><div class="empty-state svelte-1uha8ag" data-testid="empty-state"><h2 class="svelte-1uha8ag">No games found</h2> <p class="svelte-1uha8ag">There are no games available at this time.</p></div>`);
		else {
			$$renderer.push(`<!--[-1--><div class="page-header svelte-1uha8ag"><h1 class="svelte-1uha8ag">Start</h1></div> <div class="tile-grid svelte-1uha8ag"><!--[-->`);
			const each_array = ensure_array_like(games);
			for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
				let game = each_array[$$index];
				$$renderer.push(`<a${attr("href", `/games/${game.id}/setup`)} class="tile svelte-1uha8ag">`);
				if (getCoverUrl(game)) $$renderer.push(`<!--[0--><img${attr("src", getCoverUrl(game))}${attr("alt", `${stringify(game.name)} cover`)} class="tile-image svelte-1uha8ag"/>`);
				else $$renderer.push(`<!--[-1--><div class="tile-placeholder svelte-1uha8ag"><span class="placeholder-icon svelte-1uha8ag">♟</span></div>`);
				$$renderer.push(`<!--]--> <div class="tile-label svelte-1uha8ag"><span class="tile-name svelte-1uha8ag">${escape_html(game.name)}</span></div></a>`);
			}
			$$renderer.push(`<!--]--></div> <footer class="svelte-1uha8ag"><a href="/asset-reviewer" class="footer-link svelte-1uha8ag">Asset Reviewer</a></footer>`);
		}
		$$renderer.push(`<!--]--></main>`);
	});
}
//#endregion
export { _page as default };
