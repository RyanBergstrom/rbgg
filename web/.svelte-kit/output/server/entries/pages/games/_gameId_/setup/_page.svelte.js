import "../../../../../chunks/index-server.js";
import { T as escape_html, a as ensure_array_like, r as bind_props, t as attr_class, u as stringify, w as attr } from "../../../../../chunks/server.js";
import "../../../../../chunks/api.js";
//#region src/lib/game-history.ts
var BOT_DISPLAY_NAMES = [
	"Stacy",
	"Trey",
	"Bella",
	"Stitch"
];
function parseObject(value) {
	if (!value) return {};
	if (typeof value === "object") return value;
	try {
		const parsed = JSON.parse(value);
		return parsed && typeof parsed === "object" ? parsed : {};
	} catch {
		return {};
	}
}
function buildGameHistory(sessions, gameId) {
	const completed = sessions.filter((session) => Boolean(session.finished_at) && (!gameId || !session.game_id || session.game_id === gameId));
	const opponentRecords = /* @__PURE__ */ new Map();
	const history = [];
	let wins = 0;
	let losses = 0;
	let draws = 0;
	for (const session of completed) {
		const summary = parseObject(session.result_summary_json);
		const players = Array.isArray(summary.players) ? summary.players : [];
		const humanId = players[0]?.player_id || "player_1";
		const winner = session.winner || summary.winner || null;
		const result = winner === humanId ? "Win" : winner ? "Loss" : "Draw";
		if (result === "Win") wins += 1;
		else if (result === "Loss") losses += 1;
		else draws += 1;
		const opponents = players.filter((player) => player.player_id !== humanId).map((player, index) => BOT_DISPLAY_NAMES[index] || player.name || `Bot ${index + 1}`);
		for (const name of opponents) {
			const record = opponentRecords.get(name) || {
				name,
				games: 0,
				wins: 0,
				losses: 0,
				draws: 0
			};
			record.games += 1;
			if (result === "Win") record.wins += 1;
			else if (result === "Loss") record.losses += 1;
			else record.draws += 1;
			opponentRecords.set(name, record);
		}
		const scores = parseObject(session.final_scores_json);
		const summaryScores = summary.scores && typeof summary.scores === "object" ? summary.scores : {};
		const humanScore = scores[humanId] ?? summaryScores[humanId];
		history.push({
			id: session.id,
			date: session.finished_at || session.started_at || null,
			result,
			opponents,
			score: typeof humanScore === "number" ? humanScore : null
		});
	}
	const gamesPlayed = completed.length;
	return {
		gamesPlayed,
		wins,
		losses,
		draws,
		winRate: gamesPlayed ? Math.round(wins / gamesPlayed * 100) : 0,
		opponents: [...opponentRecords.values()].sort((a, b) => BOT_DISPLAY_NAMES.indexOf(a.name) - BOT_DISPLAY_NAMES.indexOf(b.name)),
		history
	};
}
//#endregion
//#region src/routes/games/[gameId]/setup/+page.svelte
function _page($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		let coverImageUrl;
		let data = $$props["data"];
		let gameId = data?.gameId || "{gameId}";
		let newPlayerName = "Ryan";
		let playerCount = gameId === "bus" ? 3 : 2;
		let selectedCampaign = "";
		let selectedScenario = "";
		let activeSessions = [];
		let gameHistory = buildGameHistory([], gameId);
		$: coverImageUrl = null;
		$$renderer.push(`<div class="setup-page svelte-1rlekqw">`);
		$$renderer.push(`<!--[-1--><div class="setup-container">`);
		if (coverImageUrl) $$renderer.push(`<!--[0--><div class="cover-hero svelte-1rlekqw"><img${attr("src", coverImageUrl)}${attr("alt", `${stringify(gameId)} cover`)} class="cover-image svelte-1rlekqw"/> <div class="cover-overlay svelte-1rlekqw"><h1 class="cover-title svelte-1rlekqw">${escape_html(gameId)}</h1></div></div>`);
		else $$renderer.push(`<!--[-1--><div class="text-hero svelte-1rlekqw"><h1 class="svelte-1rlekqw">${escape_html(gameId)}</h1></div>`);
		$$renderer.push(`<!--]--> <div class="content-area svelte-1rlekqw"><div class="top-bar svelte-1rlekqw"><button class="exit-button svelte-1rlekqw"><span class="exit-icon svelte-1rlekqw">←</span> Exit</button></div> <div class="cards-row svelte-1rlekqw">`);
		if (activeSessions.length > 0) {
			$$renderer.push(`<!--[0--><div class="card continue-card svelte-1rlekqw"><h2 class="card-title svelte-1rlekqw">Continue Game</h2> <table class="continue-table svelte-1rlekqw" data-testid="continue-list"><thead><tr><th class="svelte-1rlekqw">Game ID</th><th class="svelte-1rlekqw">Started</th><th class="svelte-1rlekqw">Actions</th></tr></thead><tbody class="svelte-1rlekqw"><!--[-->`);
			const each_array = ensure_array_like(activeSessions);
			for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
				let session = each_array[$$index];
				$$renderer.push(`<tr class="svelte-1rlekqw"><td class="session-id svelte-1rlekqw">${escape_html(session.game_id)}</td><td class="svelte-1rlekqw">${escape_html(new Date(session.started_at).toLocaleDateString())}</td><td class="actions-cell svelte-1rlekqw"><button class="delete-btn svelte-1rlekqw">Delete</button> <a${attr("href", `/games/${gameId}/play?sessionId=${session.id}`)} class="load-link svelte-1rlekqw">Load</a></td></tr>`);
			}
			$$renderer.push(`<!--]--></tbody></table></div>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <div class="card new-game-card svelte-1rlekqw"><h2 class="card-title svelte-1rlekqw">New Game</h2> `);
		if (gameId === "fields_of_fire") {
			$$renderer.push(`<!--[0--><div class="form-group svelte-1rlekqw"><label for="campaign" class="svelte-1rlekqw">Campaign</label> `);
			$$renderer.select({
				id: "campaign",
				value: selectedCampaign,
				class: ""
			}, ($$renderer) => {
				$$renderer.push("<!--[-1-->");
				$$renderer.option({
					value: "training",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Training Missions`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "normandy",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Normandy`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "naktong",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Naktong River`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "heartbreak",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Heartbreak Ridge`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "vietnam",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Vietnam`);
				}, "svelte-1rlekqw");
				$$renderer.push(`<!--]-->`);
			}, "svelte-1rlekqw");
			$$renderer.push(`</div> <div class="form-group svelte-1rlekqw"><label for="scenario" class="svelte-1rlekqw">Scenario/Mission</label> `);
			$$renderer.select({
				id: "scenario",
				value: selectedScenario,
				class: ""
			}, ($$renderer) => {
				$$renderer.push("<!--[-1-->");
				$$renderer.option({
					value: "",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Select a scenario...`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "training_1",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`Basic Training - Movement`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "pac_run1",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`PAC Run 1: Activation &amp; Movement`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "pac_run2",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`PAC Run 2: Attacking an Enemy Position`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "pac_run3",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`PAC Run 3: Potential Contact`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "cac_run1",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`CAC Run 1: Assaulting a Known Position`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "cac_run2",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`CAC Run 2: Potential Contact System`);
				}, "svelte-1rlekqw");
				$$renderer.push(` `);
				$$renderer.option({
					value: "cac_run3",
					class: ""
				}, ($$renderer) => {
					$$renderer.push(`CAC Run 3: Adding Communications`);
				}, "svelte-1rlekqw");
				$$renderer.push(`<!--]-->`);
			}, "svelte-1rlekqw");
			$$renderer.push(`</div>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <div class="form-group svelte-1rlekqw"><label for="player-name" class="svelte-1rlekqw">Player Name</label> <input id="player-name" type="text"${attr("value", newPlayerName)} placeholder="Enter your name" minlength="1" maxlength="20" class="svelte-1rlekqw"/></div> `);
		if (gameId === "bus") $$renderer.push(`<!--[0--><div class="form-group svelte-1rlekqw"><label for="player-count" class="svelte-1rlekqw">Number of Players</label> <input id="player-count" type="number"${attr("value", playerCount)}${attr("min", 3)}${attr("max", gameId === "bus" ? 5 : 2)} step="1" aria-describedby="player-count-help" class="svelte-1rlekqw"/> <small id="player-count-help">Choose from ${escape_html(3)} to ${escape_html(gameId === "bus" ? 5 : 2)} players.</small></div>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <button class="start-button svelte-1rlekqw"${attr("disabled", !newPlayerName.trim(), true)}>Start Game</button></div></div> <section class="card history-card svelte-1rlekqw" data-testid="game-history"><h2 class="card-title svelte-1rlekqw">${escape_html(gameId)} History</h2> <div class="history-stats svelte-1rlekqw" aria-label="All-time completed game statistics"><div class="stat-tile svelte-1rlekqw"><span class="svelte-1rlekqw">Completed</span><strong class="svelte-1rlekqw">${escape_html(gameHistory.gamesPlayed)}</strong></div> <div class="stat-tile svelte-1rlekqw"><span class="svelte-1rlekqw">Wins</span><strong class="svelte-1rlekqw">${escape_html(gameHistory.wins)}</strong></div> <div class="stat-tile svelte-1rlekqw"><span class="svelte-1rlekqw">Losses</span><strong class="svelte-1rlekqw">${escape_html(gameHistory.losses)}</strong></div> <div class="stat-tile svelte-1rlekqw"><span class="svelte-1rlekqw">Win rate</span><strong class="svelte-1rlekqw">${escape_html(gameHistory.gamesPlayed ? `${gameHistory.winRate}%` : "—")}</strong></div></div> `);
		if (gameHistory.gamesPlayed === 0) $$renderer.push(`<!--[0--><p class="history-empty svelte-1rlekqw">Completed games will appear here. Games still in progress are not included.</p>`);
		else {
			$$renderer.push(`<!--[-1--><h3 class="history-subtitle svelte-1rlekqw">Record against each bot</h3> <div class="history-table-wrap svelte-1rlekqw"><table class="history-table svelte-1rlekqw" data-testid="opponent-records"><thead><tr><th class="svelte-1rlekqw">Opponent</th><th class="svelte-1rlekqw">Games</th><th class="svelte-1rlekqw">W–L–D</th><th class="svelte-1rlekqw">Win rate</th></tr></thead><tbody><!--[-->`);
			const each_array_4 = ensure_array_like(gameHistory.opponents);
			for (let $$index_4 = 0, $$length = each_array_4.length; $$index_4 < $$length; $$index_4++) {
				let opponent = each_array_4[$$index_4];
				$$renderer.push(`<tr><td class="svelte-1rlekqw">${escape_html(opponent.name)}</td><td class="svelte-1rlekqw">${escape_html(opponent.games)}</td><td class="svelte-1rlekqw">${escape_html(opponent.wins)}–${escape_html(opponent.losses)}–${escape_html(opponent.draws)}</td><td class="svelte-1rlekqw">${escape_html(Math.round(opponent.wins / opponent.games * 100))}%</td></tr>`);
			}
			$$renderer.push(`<!--]--></tbody></table></div> <h3 class="history-subtitle svelte-1rlekqw">Completed games</h3> <div class="history-table-wrap svelte-1rlekqw"><table class="history-table svelte-1rlekqw" data-testid="completed-games"><thead><tr><th class="svelte-1rlekqw">Finished</th><th class="svelte-1rlekqw">Result</th><th class="svelte-1rlekqw">Opponents</th><th class="svelte-1rlekqw">Your score</th></tr></thead><tbody><!--[-->`);
			const each_array_5 = ensure_array_like(gameHistory.history);
			for (let $$index_5 = 0, $$length = each_array_5.length; $$index_5 < $$length; $$index_5++) {
				let entry = each_array_5[$$index_5];
				$$renderer.push(`<tr><td class="svelte-1rlekqw">${escape_html(entry.date ? new Date(entry.date).toLocaleDateString() : "—")}</td><td class="svelte-1rlekqw"><span${attr_class("result-pill svelte-1rlekqw", void 0, {
					"result-win": entry.result === "Win",
					"result-loss": entry.result === "Loss"
				})}>${escape_html(entry.result)}</span></td><td class="svelte-1rlekqw">${escape_html(entry.opponents.join(", ") || "—")}</td><td class="svelte-1rlekqw">${escape_html(entry.score ?? "—")}</td></tr>`);
			}
			$$renderer.push(`<!--]--></tbody></table></div>`);
		}
		$$renderer.push(`<!--]--></section></div></div>`);
		$$renderer.push(`<!--]--></div>`);
		bind_props($$props, { data });
	});
}
//#endregion
export { _page as default };
