import { r as onDestroy, t as createEventDispatcher } from "../../../../../chunks/index-server.js";
import { T as escape_html, a as ensure_array_like, d as unsubscribe_stores, jt as fallback, l as store_get, n as attr_style, r as bind_props, t as attr_class, u as stringify, w as attr } from "../../../../../chunks/server.js";
import "../../../../../chunks/api.js";
import "../../../../../chunks/dev.js";
import { n as fofCommand } from "../../../../../chunks/fofCommand.js";
import { t as settings } from "../../../../../chunks/settings.js";
//#endregion
//#region src/lib/components/games/fields_of_fire/CommandPanel.svelte
function CommandPanel($$renderer, $$props) {
	$$renderer.component(($$renderer) => {
		let activateMoves, readyIds, hqRows, advanceMove, commandStripMoves, visible, fireMoves, vofMoves, vofOrigins, vofTargets, vofRatings, commandCategories;
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
		const ACTION_CATEGORY = {
			"activate_a_subordinate_hq_or_staff": "cmd_ctrl",
			"exhort": "cmd_ctrl",
			"deploy_pyrotechnic": "cmd_ctrl",
			"reconstitute_a_plt_hq": "cmd_ctrl",
			"reconstitute_the_co_hq": "cmd_ctrl",
			"create_a_runner": "cmd_ctrl",
			"dispatch_a_runner": "cmd_ctrl",
			"dismiss_a_runner": "cmd_ctrl",
			"activate_for_at_combat_&_vehicle_movement": "cmd_ctrl",
			"switch_radio_phone_to_a_different_network": "cmd_ctrl",
			"repair_a_cut_phone_line": "cmd_ctrl",
			"designate_a_new_tactical_control": "cmd_ctrl",
			"move_to_an_adjacent_card": "movement",
			"move_a_platoon_to_an_adjacent_card": "movement",
			"attempt_to_infiltrate_an_adjacent_card": "movement",
			"attempt_to_have_a_platoon_infiltrate_an_adjacent_card": "movement",
			"attempt_to_seek_cover": "movement",
			"move_within_a_card": "movement",
			"attempt_to_infiltrate_within_a_card": "movement",
			"pick_up_load_unload_embark": "movement",
			"attempt_to_remove_a_pinned_marker": "rally",
			"attempt_to_convert_a_paralyzed_team_to_a_litter_team": "rally",
			"attempt_to_convert_a_litter_team_to_a_fire_team": "rally",
			"attempt_to_convert_a_fire_team_to_an_assault_team": "rally",
			"convert_an_assault_team_to_a_fire_team": "rally",
			"attempt_to_flip_a_unit_with_a_fire_team_side_to_front": "rally",
			"detach_team": "rally",
			"supplement_squad": "rally",
			"attempt_to_reconstitute_squad": "rally",
			"flip_a_unit_with_a_fire_team_side_to_its_fire_team_side": "rally",
			"attempt_to_spot": "combat",
			"attempt_to_concentrate_fire": "combat",
			"attempt_to_have_a_platoon_concentrate_fire": "combat",
			"attempt_to_make_a_grenade_attack": "combat",
			"attempt_to_throw_a_demolition_charge": "combat",
			"place_a_demolition_charge": "combat",
			"flamethrower_attack": "combat",
			"attempt_to_have_a_platoon_make_a_grenade_attack": "combat",
			"attempt_to_call_for_fire_from_an_off_map_firing_agency_includes_air_strikes_and_attack_helicopters": "combat",
			"call_for_indirect_fire_from_an_on_map_mortar": "combat",
			"cease_fire": "combat",
			"shift_fire": "combat",
			"fire_fpf_fpl": "combat"
		};
		const CATEGORY_ORDER = [
			"cmd_ctrl",
			"movement",
			"rally",
			"combat"
		];
		const CATEGORY_LABELS = {
			"cmd_ctrl": "Command & Control",
			"movement": "Movement",
			"rally": "Rally",
			"combat": "Combat"
		};
		function isMovementAction(type) {
			return type === "move_to_an_adjacent_card" || type === "move_a_platoon_to_an_adjacent_card";
		}
		function commandActionLabel(move) {
			if (move.type === "activate_hq") return `Act ${abbr(hqLabels[move.hq_id] || move.hq_id)}`;
			return String(move.type || move.move_id || "Action").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
		}
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
		$: commandStripMoves = [...new Map((legalMoves || []).filter((m) => {
			if ([
				"draw_commands",
				"spend_command",
				"advance_phase",
				"move_unit",
				"move_stack",
				"place_unit",
				"place_vof",
				"infiltrate",
				"fire"
			].includes(m.type)) return false;
			if (selectedCommander && m.originator_hq_id !== selectedCommander) return false;
			return true;
		}).map((m) => [m.move_id, m])).values()];
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
		$: commandCategories = (() => {
			const byCat = /* @__PURE__ */ new Map();
			for (const move of commandStripMoves) {
				const cat = ACTION_CATEGORY[move.type] || "combat";
				if (!byCat.has(cat)) byCat.set(cat, []);
				byCat.get(cat).push(move);
			}
			return CATEGORY_ORDER.filter((k) => byCat.has(k)).map((k) => {
				const byType = /* @__PURE__ */ new Map();
				for (const m of byCat.get(k)) {
					if (!byType.has(m.type)) byType.set(m.type, []);
					byType.get(m.type).push(m);
				}
				return {
					key: k,
					label: CATEGORY_LABELS[k],
					groups: [...byType.entries()].map(([type, moves]) => ({
						type,
						moves
					}))
				};
			});
		})();
		if (phaseName === "friendly_higher_hq_event" && advanceMove) $$renderer.push(`<!--[0--><section class="command-panel svelte-1kjy6xs" aria-label="Higher HQ Event controls"><div class="cp-row svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">HQ Event (T2+)</span> <button type="button" class="cp-btn cp-next svelte-1kjy6xs">Continue</button> <button type="button" class="cp-btn cp-exit svelte-1kjy6xs">Exit</button></div></section>`);
		else $$renderer.push("<!--[-1-->");
		$$renderer.push(`<!--]--> `);
		if (visible) {
			$$renderer.push(`<!--[0--><section class="command-panel svelte-1kjy6xs" aria-label="Command controls"><div class="cp-row cp-order svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Order:</span> <div class="cp-hq-strip svelte-1kjy6xs"><!--[-->`);
			const each_array = ensure_array_like(hqRows);
			for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
				let row = each_array[$$index];
				$$renderer.push(`<div class="cp-hq-group"><button type="button"${attr_class(`cp-btn cp-hq cp-${stringify(row.state)}`, "svelte-1kjy6xs", { "cp-expanded": selectedCommander === row.id })}${attr("disabled", row.state === "waiting", true)}${attr("title", row.state === "waiting" ? "Waiting: an earlier HQ must activate first" : row.state === "done" ? row.pool > 0 ? "Click to use a command" : row.draw ? "Click to draw commands" : "Already activated this turn" : row.id === hqOrder[0] || activated.length === 0 ? "Click to activate (free)" : "Click a commander to activate")}>${escape_html(row.label)} <small class="svelte-1kjy6xs">${escape_html(row.state === "done" ? row.pool > 0 ? `${row.pool} Available` : row.draw ? "Draw" : "finished" : row.state === "ready" ? "Ready" : "finished")}</small></button></div>`);
			}
			$$renderer.push(`<!--]--></div> <div class="cp-utilities svelte-1kjy6xs">`);
			if (selectedCommander !== null) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-collapse svelte-1kjy6xs"${attr("aria-expanded", true)}${attr("title", "Hide actions to reveal the board")}>${escape_html("Hide actions")}</button>`);
			else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> <button type="button" class="cp-btn cp-exit svelte-1kjy6xs">Exit</button> `);
			if (advanceMove) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-next svelte-1kjy6xs">End Cmd</button>`);
			else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> <button type="button" class="cp-btn cp-undo svelte-1kjy6xs"${attr("disabled", !canUndo, true)}>Undo</button></div></div> `);
			if (selectedCommander !== null && true) {
				$$renderer.push(`<!--[0--><div class="cp-command-strip svelte-1kjy6xs"><!--[-->`);
				const each_array_1 = ensure_array_like(commandCategories);
				for (let $$index_2 = 0, $$length = each_array_1.length; $$index_2 < $$length; $$index_2++) {
					let category = each_array_1[$$index_2];
					$$renderer.push(`<section class="cp-category svelte-1kjy6xs"${attr("aria-label", category.label)}><h4 class="cp-cat-title svelte-1kjy6xs">${escape_html(category.label)}</h4> <div class="cp-category-actions svelte-1kjy6xs"><!--[-->`);
					const each_array_2 = ensure_array_like(category.groups);
					for (let $$index_1 = 0, $$length = each_array_2.length; $$index_1 < $$length; $$index_1++) {
						let group = each_array_2[$$index_1];
						$$renderer.push(`<div class="cp-cmd-group svelte-1kjy6xs">`);
						if (isMovementAction(group.type)) $$renderer.push(`<!--[0--><button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">${escape_html(commandActionLabel(group.moves[0]))}</button>`);
						else $$renderer.push(`<!--[-1--><button type="button" class="cp-btn cp-cmd svelte-1kjy6xs">${escape_html(commandActionLabel(group.moves[0]))}</button>`);
						$$renderer.push(`<!--]--></div>`);
					}
					$$renderer.push(`<!--]--></div></section>`);
				}
				$$renderer.push(`<!--]--></div>`);
			} else $$renderer.push("<!--[-1-->");
			$$renderer.push(`<!--]--> `);
			if (phaseName === "mutual_combat") {
				$$renderer.push(`<!--[0--><div class="cp-row cp-fire svelte-1kjy6xs"><span class="cp-label svelte-1kjy6xs">Fire:</span> <!--[-->`);
				const each_array_3 = ensure_array_like(fireMoves);
				for (let $$index_3 = 0, $$length = each_array_3.length; $$index_3 < $$length; $$index_3++) {
					let fire = each_array_3[$$index_3];
					$$renderer.push(`<button type="button" class="cp-btn svelte-1kjy6xs">Card ${escape_html(fire.position)}</button>`);
				}
				$$renderer.push(`<!--]--> `);
				if (fireMoves.length === 0) $$renderer.push(`<!--[0--><span class="cp-label svelte-1kjy6xs">No VOF target</span>`);
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
		let setupComplete, isHotSeatGame, currentPlayer, isHumanTurn, fofMode;
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
		$: fofMode = !!store_get($$store_subs ??= {}, "$fofCommand", fofCommand) && [
			"friendly_higher_hq_event",
			"friendly_command",
			"mutual_combat"
		].includes(store_get($$store_subs ??= {}, "$fofCommand", fofCommand).phaseName) && true;
		$: if (currentPlayer);
		$: if (isHumanTurn && aiInterval) {
			clearInterval(aiInterval);
			aiInterval = null;
		}
		$$renderer.push(`<div${attr_class("play-shell svelte-ndk0f", void 0, { "fof-mode": fofMode })}><div class="game-container svelte-ndk0f">`);
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
		$$renderer.push(`<!----></div> `);
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
