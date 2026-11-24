import { r as onDestroy, t as createEventDispatcher } from "../../../../../chunks/index-server.js";
import { At as fallback, T as escape_html, a as ensure_array_like, d as unsubscribe_stores, l as store_get, n as attr_style, r as bind_props, t as attr_class, u as stringify, w as attr } from "../../../../../chunks/server.js";
import "../../../../../chunks/api.js";
import "../../../../../chunks/dev.js";
import { t as fofCommand } from "../../../../../chunks/fofCommand.js";
import { t as settings } from "../../../../../chunks/settings.js";
//#endregion
//#region src/lib/components/games/fields_of_fire/CommandPanel.svelte
function CommandPanel($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		let activateMoves, readyIds, hqRows, advanceMove, visible, fireMoves, vofMoves, vofOrigins, vofTargets, vofRatings, infiltrateMoves, infilUnits, infilDests, selectedInfil;
		let legalMoves = fallback($$props["legalMoves"], () => [], true);
		let activated = fallback($$props["activated"], () => [], true);
		let hqLabels = fallback($$props["hqLabels"], () => ({}), true);
		let phaseName = fallback($$props["phaseName"], null);
		let hqOrder = fallback($$props["hqOrder"], () => [], true);
		let pools = fallback($$props["pools"], () => ({}), true);
		let lastFire = fallback($$props["lastFire"], null);
		let canUndo = fallback($$props["canUndo"], false);
		let dispatchMove = fallback($$props["dispatchMove"], (move) => {});
		createEventDispatcher();
		let selectedCommander = null;
		function abbr(label) {
			return String(label).replace("Battalion HQ", "BN HQ").replace("Company HQ", "CO HQ").replace("Company Executive Officer", "CO XO").replace("Company First Sergeant", "CO 1SG").replace("Platoon HQ", "PLT HQ");
		}
		let vofOrigin = null;
		let vofTarget = null;
		let vofRating = null;
		let infilUnit = null;
		let infilDest = null;
		$: activateMoves = legalMoves.filter((m) => m.type === "activate_hq");
		$: readyIds = new Set(activateMoves.map((m) => m.hq_id));
		$: hqRows = hqOrder.map((id) => ({
			id,
			label: abbr(hqLabels[id] || id),
			state: activated.includes(id) ? "done" : readyIds.has(id) ? "ready" : "waiting",
			move: activateMoves.find((m) => m.hq_id === id),
			pool: pools[id] ?? 0,
			draw: legalMoves.find((m) => m.type === "draw_commands" && m.hq_id === id),
			spend: legalMoves.find((m) => m.type === "spend_command" && m.hq_id === id)
		}));
		$: advanceMove = legalMoves.find((m) => m.type === "advance_phase");
		$: if (legalMoves) selectedCommander = null;
		$: visible = phaseName === "friendly_command" || phaseName === "mutual_combat";
		$: fireMoves = legalMoves.filter((m) => m.type === "fire");
		$: vofMoves = legalMoves.filter((m) => m.type === "place_vof");
		$: vofOrigins = [...new Set(vofMoves.map((m) => m.from_position))].sort((a, b) => a - b);
		$: if (!vofOrigins.includes(vofOrigin)) vofOrigin = vofOrigins[0] ?? null;
		$: vofTargets = [...new Set(vofMoves.filter((m) => m.from_position === vofOrigin).map((m) => m.position))].sort((a, b) => a - b);
		$: if (!vofTargets.includes(vofTarget)) vofTarget = vofTargets[0] ?? null;
		$: vofRatings = vofMoves.filter((m) => m.from_position === vofOrigin && m.position === vofTarget).map((m) => m.rating);
		$: if (!vofRatings.includes(vofRating)) vofRating = vofRatings[0] ?? null;
		$: vofMoves.find((m) => m.from_position === vofOrigin && m.position === vofTarget && m.rating === vofRating);
		$: infiltrateMoves = legalMoves.filter((m) => m.type === "infiltrate");
		$: infilUnits = [...new Set(infiltrateMoves.map((m) => m.unit_id))];
		$: if (!infilUnits.includes(infilUnit)) infilUnit = infilUnits[0] ?? null;
		$: infilDests = infiltrateMoves.filter((m) => m.unit_id === infilUnit).map((m) => m.to_position);
		$: if (!infilDests.includes(infilDest)) infilDest = infilDests[0] ?? null;
		$: selectedInfil = infiltrateMoves.find((m) => m.unit_id === infilUnit && m.to_position === infilDest);
		if (phaseName === "friendly_higher_hq_event" && advanceMove) $$renderer.push(`<!--[0--><section class="command-panel svelte-1kjy6xs" aria-label="Higher HQ Event controls"><div class="cp-row svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">HQ Event (T2+)</span> <button type="button" class="cp-btn cp-next svelte-1kjy6xs">Continue</button> <button type="button" class="cp-btn cp-exit svelte-1kjy6xs">Exit</button></div></section>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (visible) {
			$$renderer.push(`<!--[0--><section class="command-panel svelte-1kjy6xs" aria-label="Command controls"><div class="cp-row cp-order svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Order:</span> <!--[-->`);
			const each_array = ensure_array_like(hqRows);
			for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
				let row = each_array[$$index];
				$$renderer.push(`<div class="cp-hq-group"><button type="button"${attr_class(`cp-btn cp-hq cp-${stringify(row.state)}`, "svelte-1kjy6xs", { "cp-expanded": selectedCommander === row.id })}${attr("disabled", row.state === "waiting", true)}${attr("title", row.state === "waiting" ? "Waiting: an earlier HQ must activate first" : row.state === "done" ? row.pool > 0 ? "Click to use a command" : row.draw ? "Click to draw commands" : "Already activated this turn" : row.id === hqOrder[0] ? "Click to activate (free)" : "Click a commander to activate")}>${escape_html(row.label)} <small class="svelte-1kjy6xs">${escape_html(row.state === "done" ? row.pool > 0 ? `${row.pool} Available` : row.draw ? "Draw" : "finished" : row.state === "ready" ? "Waiting" : "finished")}</small></button></div>`);
			}
			$$renderer.push(`<!--]--> <div class="cp-exit-group svelte-1kjy6xs"><button type="button" class="cp-btn cp-exit svelte-1kjy6xs">Exit</button> `);
			if (advanceMove) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-next svelte-1kjy6xs">End Cmd</button>`);
			else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> <button type="button" class="cp-btn cp-undo svelte-1kjy6xs"${attr("disabled", !canUndo, true)}>Undo</button></div></div> `);
			if (selectedCommander !== null) {
				$$renderer.push(`<!--[0--><div class="cp-command-strip svelte-1kjy6xs"><div class="cp-command-list svelte-1kjy6xs"><!--[-->`);
				const each_array_1 = ensure_array_like(legalMoves.filter((m) => m.type === "activate_hq" && !activated.includes(m.hq_id)));
				for (let $$index_1 = 0, $$length = each_array_1.length; $$index_1 < $$length; $$index_1++) {
					let m = each_array_1[$$index_1];
					$$renderer.push(`<button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">Act ${escape_html(abbr(hqLabels[m.hq_id] || m.hq_id))}</button>`);
				}
				$$renderer.push(`<!--]--> `);
				if (legalMoves.some((m) => m.type === "exhort")) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">Exhort</button>`);
				else $$renderer.push("<!--[-1-->");
				$$renderer.push(`<!--]--> `);
				if (legalMoves.some((m) => m.type === "reconstitute")) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">Reconstitute</button>`);
				else $$renderer.push("<!--[-1-->");
				$$renderer.push(`<!--]--> `);
				if (legalMoves.some((m) => m.type === "create_runner")) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">Create Runner</button>`);
				else $$renderer.push("<!--[-1-->");
				$$renderer.push(`<!--]--></div></div>`);
			} else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> `);
			if (infiltrateMoves.length > 0) {
				$$renderer.push(`<!--[0--><div class="cp-row cp-infil svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Infiltrate to</span> `);
				$$renderer.select({
					value: infilUnit,
					"aria-label": "Infiltrate unit"
				}, ($$renderer) => {
					$$renderer.push(`<!--[-->`);
					const each_array_2 = ensure_array_like(infilUnits);
					for (let $$index_2 = 0, $$length = each_array_2.length; $$index_2 < $$length; $$index_2++) {
						let uid = each_array_2[$$index_2];
						$$renderer.option({ value: uid }, ($$renderer) => {
							$$renderer.push(`${escape_html(uid)}`);
						});
					}
					$$renderer.push(`<!--]-->`);
				});
				$$renderer.push(` `);
				$$renderer.select({
					value: infilDest,
					"aria-label": "Infiltrate destination"
				}, ($$renderer) => {
					$$renderer.push(`<!--[-->`);
					const each_array_3 = ensure_array_like(infilDests);
					for (let $$index_3 = 0, $$length = each_array_3.length; $$index_3 < $$length; $$index_3++) {
						let dest = each_array_3[$$index_3];
						$$renderer.option({ value: dest }, ($$renderer) => {
							$$renderer.push(`Card ${escape_html(dest)}`);
						});
					}
					$$renderer.push(`<!--]-->`);
				});
				$$renderer.push(` <button type="button" class="cp-btn svelte-1kjy6xs"${attr("disabled", !selectedInfil, true)}>Infiltrate</button></div>`);
			} else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> `);
			if (phaseName === "mutual_combat") {
				$$renderer.push(`<!--[0--><div class="cp-row cp-fire svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Fire:</span> <!--[-->`);
				const each_array_4 = ensure_array_like(fireMoves);
				for (let $$index_4 = 0, $$length = each_array_4.length; $$index_4 < $$length; $$index_4++) {
					let fire = each_array_4[$$index_4];
					$$renderer.push(`<button type="button" class="cp-btn svelte-1kjy6xs">Card ${escape_html(fire.position)}</button>`);
				}
				$$renderer.push(`<!--]--> `);
				if (fireMoves.length === 0) $$renderer.push(`<!--[0--><span class="cp-label svelte-1kjy6xs">no VOF target</span>`);
				else $$renderer.push("<!--[-1-->");
				$$renderer.push(`<!--]--></div> `);
				if (lastFire) $$renderer.push(`<!--[0--><div class="cp-row cp-lastdraw svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Last fire:</span> <strong>card ${escape_html(lastFire.position)}</strong> <span>net ${escape_html(lastFire.net_modifier)}, result <strong class="cp-pool svelte-1kjy6xs">${escape_html(lastFire.result)}</strong></span></div>`);
				else $$renderer.push("<!--[-1-->");
				$$renderer.push(`<!--]-->`);
			} else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--></section>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]-->`);
		bind_props($$props, {
			legalMoves,
			activated,
			hqLabels,
			phaseName,
			hqOrder,
			pools,
			lastFire,
			canUndo,
			dispatchMove
		});
	});
}
//#endregion
//#region src/lib/components/GameProgressPanel.svelte
function GameProgressPanel($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		var $$store_subs;
		let phase, currentPlayer, winner, confirmRequired, isSetupPhase, fofMode;
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
		$: fofMode = !!store_get($$store_subs ??= {}, "$fofCommand", fofCommand) && [
			"friendly_higher_hq_event",
			"friendly_command",
			"mutual_combat"
		].includes(store_get($$store_subs ??= {}, "$fofCommand", fofCommand).phaseName) && !winner;
		$: if (phase) phase.phase_name, phase.confirm_required;
		$$renderer.push(`<div${attr_class("game-progress-panel svelte-5gzb49", void 0, { "fof-mode": fofMode })}>`);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <div class="panel-row svelte-5gzb49">`);
		if (!fofMode) {
			$$renderer.push(`<!--[0--><div class="panel-left svelte-5gzb49"><button class="settings-button svelte-5gzb49" title="Settings"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg></button> `);
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
			$$renderer.push(`<!--]--></div>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> <div class="panel-right svelte-5gzb49">`);
		if (store_get($$store_subs ??= {}, "$fofCommand", fofCommand)) {
			$$renderer.push(`<!--[0--><div class="footer-commands svelte-5gzb49">`);
			CommandPanel($$renderer, {
				legalMoves: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).legalMoves,
				pools: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).pools,
				lastFire: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).lastFire,
				activated: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).activated,
				hqLabels: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).hqLabels,
				hqOrder: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).hqOrder,
				phaseName: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).phaseName,
				canUndo,
				dispatchMove: store_get($$store_subs ??= {}, "$fofCommand", fofCommand).dispatchMove
			});
			$$renderer.push(`<!----></div>`);
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (gameId === "fields_of_fire" && isSetupPhase && !winner) $$renderer.push(`<!--[0--><button class="start-mission-btn-panel svelte-5gzb49"${attr("disabled", !setupComplete, true)}>Start Mission</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (confirmRequired || pendingMove) $$renderer.push(`<!--[0--><button class="confirm-button svelte-5gzb49"${attr("disabled", !pendingMove && !confirmRequired, true)}>${escape_html(pendingMove ? "Confirm Move" : phase?.confirm_name || "Confirm")}</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if ((canUndo || pendingMove) && !fofMode) $$renderer.push(`<!--[0--><button class="undo-button svelte-5gzb49"${attr("disabled", !pendingMove && !canUndo, true)}>Undo</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (!fofMode) $$renderer.push(`<!--[0--><button class="exit-button svelte-5gzb49">Exit</button>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--></div></div></div>`);
		if ($$store_subs) unsubscribe_stores($$store_subs);
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
//#region src/lib/components/GameAuditLog.svelte
function GameAuditLog($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		let entries = fallback($$props["entries"], () => [], true);
		$$renderer.push(`<div${attr_class("audit-log svelte-1ky4epb", void 0, { "expanded": false })}><button class="audit-toggle svelte-1ky4epb">${escape_html("▸")} Audit Log (${escape_html(entries.length)})</button> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--></div> "`);
		bind_props($$props, { entries });
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
		let auditLog = [];
		const HUMAN_PLAYER = "player_1";
		const HOT_SEAT_GAME = null;
		onDestroy(() => {
			if (aiInterval) clearInterval(aiInterval);
		});
		$: setupComplete = (() => {
			if (gameId !== "fields_of_fire") return false;
			const requiredUnits = ({}.company?.units || []).filter((u) => u.setup_required !== false);
			return requiredUnits.filter((u) => u.position !== null && u.position !== void 0).length === requiredUnits.length && requiredUnits.length > 0;
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
		if (gameId !== "fields_of_fire") {
			$$renderer.push("<!--[0-->");
			GameAuditLog($$renderer, { entries: auditLog });
		} else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		$$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]-->`);
		if ($$store_subs) unsubscribe_stores($$store_subs);
		bind_props($$props, { data });
	});
}
//#endregion
export { _page as default };
