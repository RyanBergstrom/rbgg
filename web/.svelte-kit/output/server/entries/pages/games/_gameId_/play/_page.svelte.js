import { r as onDestroy, t as createEventDispatcher } from "../../../../../chunks/index-server.js";
import { At as fallback, T as escape_html, d as unsubscribe_stores, l as store_get, n as attr_style, r as bind_props, u as stringify, w as attr } from "../../../../../chunks/server.js";
import "../../../../../chunks/api.js";
import "../../../../../chunks/dev.js";
import { t as settings } from "../../../../../chunks/settings.js";
//#endregion
//#region src/lib/components/GameProgressPanel.svelte
function GameProgressPanel($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		let phase, currentPlayer, winner, confirmRequired, isSetupPhase;
		let game = fallback($$props["game"], null);
		let screenState = fallback($$props["screenState"], null);
		let pendingMove = fallback($$props["pendingMove"], null);
		let canUndo = fallback($$props["canUndo"], false);
		let setupComplete = fallback($$props["setupComplete"], false);
		let gameId = fallback($$props["gameId"], null);
		createEventDispatcher();
		function getPlayerName(playerId) {
			if (!playerId) return "Unknown";
			if (playerId === "player_1") return "Red";
			if (playerId === "player_2") return "Green";
			if (playerId === "player_3") return "Blue";
			if (playerId === "player_4") return "Yellow";
			if (playerId === "player_5") return "Black";
			return playerId;
		}
		function getPlayerColor(playerId) {
			if (playerId === "player_1") return "#cc0000";
			if (playerId === "player_2") return "#3b8d3b";
			if (playerId === "player_3") return "#1d70b8";
			if (playerId === "player_4") return "#e0a800";
			if (playerId === "player_5") return "#333333";
			return "#666";
		}
		$: phase = screenState?.phase || null;
		$: currentPlayer = screenState?.current_player || game?.state?.player_turn || null;
		$: winner = screenState?.winner || game?.state?.winner || null;
		$: confirmRequired = phase?.confirm_required || false;
		$: isSetupPhase = phase?.phase_name === "setup" || game?.state?.game_data?.phase === "setup";
		$: if (phase) phase.phase_name, phase.confirm_required;
		$$renderer.push(`<div class="game-progress-panel svelte-5gzb49">> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <div class="panel-row svelte-5gzb49"><div class="panel-left svelte-5gzb49"><button class="settings-button svelte-5gzb49" title="Settings"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg></button> `);
		if (winner) $$renderer.push(`<!--[0--><span class="player-dot svelte-5gzb49"${attr_style(`background: ${stringify(getPlayerColor(winner))}`)}></span> <strong>${escape_html(getPlayerName(winner))} wins!</strong>`);
		else if (currentPlayer) $$renderer.push(`<!--[1--><span class="player-dot svelte-5gzb49"${attr_style(`background: ${stringify(getPlayerColor(currentPlayer))}`)}></span> <span>${escape_html(getPlayerName(currentPlayer))}'s turn</span>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (phase && !winner) {
			$$renderer.push(`<!--[0--><span class="phase-status svelte-5gzb49"><span class="phase-name svelte-5gzb49">${escape_html(phase.phase_name)}</span> `);
			if (phase.phase_text) $$renderer.push(`<!--[0--><span class="phase-text svelte-5gzb49">— ${escape_html(phase.phase_text)}</span>`);
			else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--></span>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--></div> <div class="panel-right svelte-5gzb49">`);
		if (gameId === "fields_of_fire" && isSetupPhase && !winner) $$renderer.push(`<!--[0--><button class="start-mission-btn-panel svelte-5gzb49"${attr("disabled", !setupComplete, true)}>Start Mission</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (confirmRequired || pendingMove) $$renderer.push(`<!--[0--><button class="confirm-button svelte-5gzb49"${attr("disabled", !pendingMove && !confirmRequired, true)}>${escape_html(pendingMove ? "Confirm Move" : phase?.confirm_name || "Confirm")}</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (canUndo || pendingMove) $$renderer.push(`<!--[0--><button class="undo-button svelte-5gzb49"${attr("disabled", !pendingMove && !canUndo, true)}>Undo</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <button class="exit-button svelte-5gzb49">Exit</button></div></div></div>`);
		bind_props($$props, {
			game,
			screenState,
			pendingMove,
			canUndo,
			setupComplete,
			gameId
		});
	});
}
//#endregion
//#region src/routes/games/[gameId]/play/+page.svelte
function _page($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		var $$store_subs;
		let setupComplete, isHotSeatGame, currentPlayer, isHumanTurn;
		let data = $$props["data"];
		let gameId = data?.gameId || "{gameId}";
		data?.sessionId;
		let game = null;
		let screenState = null;
		let aiInterval = null;
		let aiProvider = "ppo";
		let aiDifficulty = "hard";
		let pendingMove = null;
		let canUndo = false;
		const HUMAN_PLAYER = "player_1";
		const HOT_SEAT_GAME = "twilight_struggle";
		onDestroy(() => {
			if (aiInterval) clearInterval(aiInterval);
		});
		$: setupComplete = (() => {
			if (gameId !== "fields_of_fire") return false;
			const units = {}.company?.units || [];
			return units.filter((u) => u.position !== null && u.position !== void 0).length === units.length && units.length > 0;
		})();
		$: isHotSeatGame = gameId === HOT_SEAT_GAME;
		$: currentPlayer = null;
		$: isHumanTurn = (isHotSeatGame || currentPlayer === HUMAN_PLAYER) && true;
		$: if (currentPlayer);
		$: if (isHumanTurn && aiInterval) {
			clearInterval(aiInterval);
			aiInterval = null;
		}
		$$renderer.push(`<div class="game-container svelte-ndk0f">`);
		if (gameId === "lost_cities" && store_get($$store_subs ??= {}, "$settings", settings).show_ai_controls !== false) {
			$$renderer.push(`<!--[0--><label class="ai-provider-control svelte-ndk0f">AI opponent `);
			$$renderer.select({
				value: aiProvider,
				class: ""
			}, ($$renderer) => {
				$$renderer.option({ value: "ppo" }, ($$renderer) => {
					$$renderer.push(`Trained PPO model (default)`);
				});
				$$renderer.option({ value: "mcts" }, ($$renderer) => {
					$$renderer.push(`MCTS`);
				});
			}, "svelte-ndk0f");
			$$renderer.push(`</label> `);
			$$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> `);
			$$renderer.push(`<!--[0--><label class="ai-provider-control svelte-ndk0f">Model difficulty `);
			$$renderer.select({
				value: aiDifficulty,
				class: ""
			}, ($$renderer) => {
				$$renderer.option({ value: "hard" }, ($$renderer) => {
					$$renderer.push(`Hard — strongest choices`);
				});
				$$renderer.option({ value: "medium" }, ($$renderer) => {
					$$renderer.push(`Medium — occasional random move`);
				});
				$$renderer.option({ value: "easy" }, ($$renderer) => {
					$$renderer.push(`Easy — more random moves`);
				});
			}, "svelte-ndk0f");
			$$renderer.push(`</label>`);
			$$renderer.push(`<!--]-->`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		$$renderer.push(`<!--[1--><div class="loading-panel svelte-ndk0f">Loading game board...</div>`);
		$$renderer.push(`<!--]--> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]-->`);
		$$renderer.push(`<!--]--></div> `);
		GameProgressPanel($$renderer, {
			game,
			screenState,
			pendingMove,
			canUndo,
			gameId,
			setupComplete
		});
		$$renderer.push(`<!----> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]-->`);
		if ($$store_subs) unsubscribe_stores($$store_subs);
		bind_props($$props, { data });
	});
}
//#endregion
export { _page as default };
