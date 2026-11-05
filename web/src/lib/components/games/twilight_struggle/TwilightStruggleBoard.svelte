<script>
  import { createEventDispatcher } from 'svelte';

  export let game = null;
  export let gameId = 'twilight_struggle';
  export let legalMoves = [];
  export let screenState = null;
  export let pendingMove = null;
  export let actionInProgress = false;

  const dispatch = createEventDispatcher();
  const FACTION_LABEL = { us: 'United States', ussr: 'Soviet Union' };
  const COLOR = { us: '#2878c7', ussr: '#d34f4f' };

  let selectedCardId = null;
  let selectedMode = 'event';
  let eventChoicesText = '{}';
  let nestedEventChoicesText = '{}';
  let operationsType = 'influence';
  let operationsCountry = '';
  let influencePoints = 1;
  let influencePlacements = [];
  let realignmentTargets = [];
  let chosenDefcon = 3;
  let formError = '';
  let mapZoom = 1;
  let eventCountry = '';
  let eventCountries = [];
  let eventCountryAmounts = {};
  let eventSourceAmounts = {};
  let eventTargetAmounts = {};
  let eventMode = 'south_africa';
  let eventChoiceValue = '';
  let includeBonusOperations = false;
  let bonusOperationsType = 'influence';
  let bonusOperationsCountry = '';
  let bonusInfluencePoints = 1;
  let bonusInfluencePlacements = [];
  let bonusRealignmentTargets = [];
  let tehranSelectedCardIds = [];

  $: view = screenState || game?.screen_state || {};
  $: data = view.game_data || {};
  $: moves = view.legal_moves?.length ? view.legal_moves : legalMoves;
  $: phase = data.current_phase || view.phase?.phase_name || 'loading';
  $: faction = data.faction_by_player?.[view.current_player] || data.current_player_faction;
  $: factionName = FACTION_LABEL[faction] || 'Player';
  $: hand = Array.isArray(data.hand) ? data.hand : [];
  $: cardMoves = moves.filter((move) => move.type === 'play_card');
  $: selectedCard = hand.find((card) => card.id === selectedCardId) || null;
  $: selectedTemplate = cardMoves.find((move) => move.card_id === selectedCardId) || null;
  $: operationsBudget = selectedMode === 'operations' ? Number(selectedCard?.operations || 0) : Number(selectedTemplate?.bonus_operations || 0);
  $: operations = data.tracks || {};
  $: countryNames = Object.keys(data.countries || {}).sort((a, b) => a.localeCompare(b));
  $: mapPositions = data.map_positions || {};
  $: countryInfo = data.country_info || {};
  $: selectedEventKey = ({ 7: 'socialist_governments', 14: 'comecon', 16: 'warsaw_pact_formed', 19: 'truman_doctrine', 22: 'independent_reds', 23: 'marshall_plan', 24: 'indo_pakistani_war', 28: 'suez_crisis', 29: 'east_european_unrests', 30: 'decolonization', 33: 'de_stalinization', 36: 'brush_war', 43: 'salt_negotiations', 45: 'summit_defcon', 47: 'junta', 49: 'missile_envy_card_id', 53: 'south_african_unrest', 63: 'colonial_rearguards', 66: 'puppet_governments', 67: 'grain_sales', 70: 'oas_founded', 74: 'the_voice_of_america', 75: 'liberation_theology', 76: 'ussuri_river_skirmish', 77: 'ask_not_what', 85: 'star_wars', 87: 'reformer', 88: 'marine_barracks_bombing', 99: 'pershing_ii_deployed', 100: 'wargames', 104: 'cambridge_five', 105: 'special_relationship', 108: 'our_man_in_tehran' })[selectedCardId] || '';
  $: ussuriRequiresPlacement = selectedCardId === 76 && data.china_card?.owner === 'us';
  $: eventCountryOptions = selectedCardId === 76 ? countryNames.filter((name) => countryInfo[name]?.region === 'Asia') :
    selectedCardId === 16 ? ['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria'].filter((name) => eventMode === 'add_ussr' || (data.countries[name]?.us || 0) > 0) :
    selectedCardId === 14 ? ['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria', 'Yugoslavia'].filter((name) => !controlledByFaction(name, 'us')) :
    selectedCardId === 23 ? countryNames.filter((name) => countryInfo[name]?.region === 'Europe' && !['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria'].includes(name) && !controlledByFaction(name, 'ussr')) :
    selectedCardId === 24 ? ['India', 'Pakistan'] :
    selectedCardId === 36 ? countryNames.filter((name) => [1, 2].includes(countryInfo[name]?.stability) && !(data.persistent_events?.nato && countryInfo[name]?.region === 'Europe' && !data.persistent_events?.nato_cancelled_countries?.includes(name) && controlledByFaction(name, 'us'))) :
    selectedCardId === 47 ? countryNames.filter((name) => ['Central America', 'South America'].includes(countryInfo[name]?.region)) :
    selectedCardId === 29 ? ['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria'].filter((name) => (data.countries[name]?.ussr || 0) >= (Number(data.turn || 1) >= 8 ? 2 : 1)) :
    selectedCardId === 19 ? countryNames.filter((name) => countryInfo[name]?.region === 'Europe' && !controlledByAny(name)) :
    selectedCardId === 22 ? ['Yugoslavia', 'Romania', 'Bulgaria', 'Hungary', 'Czechoslovakia'] :
    selectedCardId === 104 ? countryNames.filter((name) => hand.some((card) => card.scoring && card.name.toLowerCase().includes(countryInfo[name]?.region?.toLowerCase() || ''))) :
    selectedCardId === 105 ? (!controlledByFaction('U.K.', 'us') ? [] : data.persistent_events?.nato ? ['Benelux', 'Denmark', 'France', 'Italy', 'Norway', 'Spain/Portugal', 'U.K.', 'W. Germany'] : countryInfo['U.K.']?.adjacent_countries || []) :
    selectedCardId === 7 ? ['U.K.', 'Norway', 'Sweden', 'Denmark', 'Benelux', 'France', 'Spain/Portugal', 'W. Germany', 'Italy', 'Greece', 'Turkey'].filter((name) => (data.countries[name]?.us || 0) > 0) :
    selectedCardId === 87 ? countryNames.filter((name) => countryInfo[name]?.region === 'Europe') :
    selectedCardId === 28 ? ['France', 'U.K.', 'Israel'].filter((name) => (data.countries[name]?.us || 0) > 0) :
    selectedCardId === 99 ? ['Canada', 'U.K.', 'Norway', 'Sweden', 'Denmark', 'Benelux', 'France', 'Spain/Portugal', 'W. Germany', 'Italy', 'Greece', 'Turkey'].filter((name) => (data.countries[name]?.us || 0) > 0) :
    selectedCardId === 53 ? (countryInfo['South Africa']?.adjacent_countries || []) :
    selectedCardId === 66 ? countryNames.filter((name) => !(data.countries[name]?.us || 0) && !(data.countries[name]?.ussr || 0)) :
    selectedCardId === 70 ? countryNames.filter((name) => ['Central America', 'South America'].includes(countryInfo[name]?.region)) :
    selectedCardId === 74 ? countryNames.filter((name) => countryInfo[name]?.region !== 'Europe' && (data.countries[name]?.ussr || 0) > 0) :
    selectedCardId === 75 ? countryNames.filter((name) => countryInfo[name]?.region === 'Central America') :
    selectedCardId === 88 ? countryNames.filter((name) => name !== 'Lebanon' && countryInfo[name]?.region === 'Middle East' && (data.countries[name]?.us || 0) > 0) :
    selectedCardId === 77 ? hand.filter((card) => card.id !== selectedCardId).map((card) => String(card.id)) :
    countryNames.filter((name) => ['Africa', 'Southeast Asia'].includes(countryInfo[name]?.region));
  $: eventSelectionCount = selectedCardId === 76 ? 4 : selectedCardId === 16 ? (eventMode === 'remove_us' ? 4 : 3) :
    selectedCardId === 53 && eventMode === 'adjacent' ? 0 :
    selectedCardId === 87 ? (number(operations.victory_points) < 0 ? 3 : 2) :
    ({ 7: 3, 14: 4, 23: 7, 28: 3, 29: 3, 30: 4, 47: 1, 63: 4, 66: 3, 74: 4, 75: 3, 77: hand.length, 85: 0, 99: 3 })[selectedCardId] ?? 1;
  $: eventCountrySelectionLimit = selectedCardId === 99 ? 3 : selectedCardId === 76 ? 4 : eventSelectionCount;
  $: eventChoiceOptions = selectedCardId === 67 ? ['return', 'play'] :
    selectedCardId === 49 ? (() => { const eligible = (data.revealed_hands?.[faction === 'us' ? 'ussr' : 'us'] || []).filter((card) => !card.scoring); const highest = Math.max(0, ...eligible.map((card) => Number(card.operations) || 0)); return eligible.filter((card) => Number(card.operations) === highest).map((card) => String(card.id)); })() :
    selectedCardId === 43 || selectedCardId === 85 ? (data.discard_pile || []).filter((card) => !card.scoring && !card.special && (selectedCardId !== 85 || data.tracks?.space_race?.us > data.tracks?.space_race?.ussr)).map((card) => String(card.id)) :
    selectedCardId === 77 ? hand.filter((card) => card.id !== selectedCardId && card.id !== selectedCard?.id).map((card) => String(card.id)) : [];
  $: oasInfluenceTotal = Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: liberationInfluenceTotal = Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: marineRemovalTotal = Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: voiceRemovalTotal = Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: deStalinizationFromTotal = Object.values(eventSourceAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: deStalinizationToTotal = Object.values(eventTargetAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0);
  $: marineAllocationValid = marineRemovalTotal <= 2 && Object.entries(eventCountryAmounts).every(([name, amount]) => Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= Math.min(2, Number(data.countries?.[name]?.us || 0)));
  $: eventSelectionReady = isEventSelectionReady(selectedCardId, eventCountries, eventCountry, eventCountryAmounts, eventMode, eventChoiceValue, eventSelectionCount, ussuriRequiresPlacement, marineAllocationValid, oasInfluenceTotal, liberationInfluenceTotal, voiceRemovalTotal, deStalinizationFromTotal, deStalinizationToTotal, eventSourceAmounts, eventTargetAmounts, operations, data);

  function isEventSelectionReady(cardId, countries, country, amounts, mode, choiceValue, selectionCount, requiresUssuriPlacement, marineValid, oasTotal, liberationTotal, voiceTotal, sourceTotal, targetTotal, sourceAmounts, targetAmounts, tracks, gameData) {
    if ([43, 45, 49, 67, 96, 100].includes(cardId)) return true;
    if (cardId === 77) return countries.length <= Number(gameData.draw_pile?.count ?? gameData.draw_pile?.length ?? 0);
    if (cardId === 33) return sourceTotal > 0 && sourceTotal <= 4 && sourceTotal === targetTotal && Object.entries(sourceAmounts).every(([name, amount]) => Number.isInteger(Number(amount)) && Number(amount) > 0 && Number(amount) <= Number(gameData.countries?.[name]?.ussr || 0)) && Object.entries(targetAmounts).every(([name, amount]) => Number.isInteger(Number(amount)) && Number(amount) > 0 && Number(amount) <= 2 && !controlledByFaction(name, 'us'));
    if (cardId === 88) return marineValid;
    if (cardId === 70) return oasTotal === 2;
    if (cardId === 74) return voiceTotal >= 0 && voiceTotal <= 4 && Object.entries(amounts).every(([name, amount]) => gameData.country_info?.[name]?.region && gameData.country_info[name].region !== 'Europe' && Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= Math.min(2, Number(gameData.countries?.[name]?.ussr || 0)));
    if (cardId === 75) return liberationTotal === 3 && Object.values(amounts).every((amount) => Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 2);
    if (cardId === 7) return Object.values(amounts).reduce((total, amount) => total + (Number(amount) || 0), 0) === 3 && Object.entries(amounts).every(([name, amount]) => Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 2 && Number(amount) <= Number(gameData.countries?.[name]?.us || 0));
    if (cardId === 76) return gameData.china_card?.owner === 'ussr' || (requiresUssuriPlacement && countries.length >= 2 && countries.length <= 4 && countries.reduce((total, name) => total + (Number(amounts[name]) || 0), 0) === 4 && countries.every((name) => Number(amounts[name]) >= 1 && Number(amounts[name]) <= 2));
    if (cardId === 47) return Boolean(country) && ['Central America', 'South America'].includes(gameData.country_info?.[country]?.region);
    if (cardId === 87) return Object.values(amounts).reduce((total, amount) => total + (Number(amount) || 0), 0) === (Number(tracks.victory_points) < 0 ? 6 : 4) && Object.entries(amounts).every(([name, amount]) => gameData.country_info?.[name]?.region === 'Europe' && Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 2);
    if (cardId === 99) return countries.length <= 3;
    if (cardId === 16) return mode === 'remove_us' ? countries.length === 4 && countries.every((name) => Number(gameData.countries?.[name]?.us || 0) > 0) : Object.values(amounts).reduce((total, amount) => total + (Number(amount) || 0), 0) === 5 && Object.entries(amounts).every(([name, amount]) => ['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria'].includes(name) && Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 2);
    if (cardId === 85) return tracks.space_race?.us <= tracks.space_race?.ussr || Boolean(choiceValue);
    if (cardId === 28) return Object.values(amounts).reduce((total, amount) => total + (Number(amount) || 0), 0) === 4 && Object.entries(amounts).every(([name, amount]) => ['France', 'U.K.', 'Israel'].includes(name) && Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= 2 && Number(amount) <= Number(gameData.countries?.[name]?.us || 0)) && ['France', 'U.K.', 'Israel'].reduce((total, name) => total + Math.min(2, Number(gameData.countries?.[name]?.us || 0)), 0) >= 4;
    if (cardId === 53) return mode === 'south_africa' || Object.values(amounts).reduce((total, amount) => total + (Number(amount) || 0), 0) === 2;
    return selectionCount === 1 ? Boolean(country) : countries.length === selectionCount;
  }
  $: influenceTargets = countryNames.filter((country) => {
    const neighbors = countryInfo[country]?.adjacent_countries || [];
    const superpower = faction === 'us' ? 'United States' : 'USSR';
    const linkedToSuperpower = (data.superpower_adjacency || []).some((edge) => edge.includes(country) && edge.includes(superpower));
    return linkedToSuperpower || (data.countries[country]?.[faction] || 0) > 0 ||
      neighbors.some((neighbor) => (data.countries[neighbor]?.[faction] || 0) > 0);
  });
  $: coupTargets = countryNames.filter((country) => {
    const region = countryInfo[country]?.region;
    const blockedRegions = { 4: ['Europe'], 3: ['Europe', 'Asia'], 2: ['Europe', 'Asia', 'Middle East'] }[operations.defcon] || [];
    return operations.defcon > 1 && !blockedRegions.includes(region);
  });
  $: bonusOperationsEligible = [26, 47, 57, 62, 90, 91, 96].includes(selectedCardId);
  $: bonusOperationsAvailable = bonusOperationsEligible && (selectedCardId !== 90 || Boolean(data.persistent_events?.reformer));
  $: bonusOperationsFaction = [26, 96].includes(selectedCardId) ? 'us' : [62, 90, 91].includes(selectedCardId) ? 'ussr' : faction;
  $: bonusOperationsTargets = bonusOperationsType === 'coup' ? countryNames.filter((name) => Number(data.countries?.[name]?.[bonusOperationsFaction === 'us' ? 'ussr' : 'us'] || 0) > 0) : bonusOperationsType === 'realignment' ? countryNames : countryNames.filter((country) => (data.superpower_adjacency || []).some((edge) => edge.includes(country) && edge.includes(bonusOperationsFaction === 'us' ? 'United States' : 'USSR')) || (data.countries[country]?.[bonusOperationsFaction] || 0) > 0 || (countryInfo[country]?.adjacent_countries || []).some((neighbor) => (data.countries[neighbor]?.[bonusOperationsFaction] || 0) > 0));
  $: bonusOperationsBudget = (() => {
    if (selectedCardId === 26 || selectedCardId === 62) return 1;
    const base = selectedCardId === 20 ? 4 : Number(selectedCard?.operations || 0);
    const turn = Number(data.turn || 1);
    const persistent = data.persistent_events || {};
    let value = base;
    if (bonusOperationsFaction === 'us' && persistent.containment?.faction === 'us' && persistent.containment?.expires_turn === turn) value = Math.min(4, value + 1);
    if (persistent.red_scare_purge?.faction === bonusOperationsFaction && persistent.red_scare_purge?.expires_turn === turn) value = Math.max(1, value - 1);
    if (bonusOperationsFaction === 'ussr' && persistent.brezhnev_doctrine?.faction === 'ussr' && persistent.brezhnev_doctrine?.expires_turn === turn) value = Math.min(4, value + 1);
    return value;
  })();
  $: bonusOperationsCountryOptions = [47, 91, 96].includes(selectedCardId) && bonusOperationsType === 'coup'
    ? countryNames.filter((name) => {
        const opponent = bonusOperationsFaction === 'us' ? 'ussr' : 'us';
        const region = countryInfo[name]?.region;
        return Number(data.countries?.[name]?.[opponent] || 0) > 0 && (selectedCardId === 47
          ? ['Central America', 'South America'].includes(region)
          : selectedCardId === 91
            ? (countryInfo['Nicaragua']?.adjacent_countries || []).includes(name)
            : region === 'Europe');
      })
    : bonusOperationsTargets.filter((name) => selectedCardId === 47
      ? ['Central America', 'South America'].includes(countryInfo[name]?.region)
      : selectedCardId === 91
        ? (countryInfo['Nicaragua']?.adjacent_countries || []).includes(name)
        : selectedCardId === 96
          ? countryInfo[name]?.region === 'Europe'
          : true);
  $: operationTargets = operationsType === 'coup' ? coupTargets :
    operationsType === 'realignment' ? countryNames.filter((country) => {
      const region = countryInfo[country]?.region;
      const blockedRegions = { 4: ['Europe'], 3: ['Europe', 'Asia'], 2: ['Europe', 'Asia', 'Middle East'] }[operations.defcon] || [];
      return operations.defcon > 1 && !blockedRegions.includes(region);
    }) : influenceTargets;
  $: canChoose = !actionInProgress && !view.winner && !pendingMove;
  $: stagedMoves = moves.filter((move) => ['event_response', 'event_bonus', 'card_operations'].includes(move.type));
  $: hasStagedCardOperations = stagedMoves.some((move) => move.type === 'card_operations');
  $: hasStagedBonusOperations = stagedMoves.some((move) => move.type === 'event_bonus' && move.decline === false);

  function emit(move) {
    if (!canChoose || !move) return;
    formError = '';
    dispatch('select-move', move);
  }

  function submitTehranDiscards() {
    emit({ type: 'event_response', player_id: view.current_player, decision: 'discard_revealed_cards', card_ids: tehranSelectedCardIds });
  }

  function selectCard(card) {
    if (!canChoose) return;
    selectedCardId = selectedCardId === card.id ? null : card.id;
    selectedMode = 'event';
    eventChoicesText = '{}';
    nestedEventChoicesText = '{}';
    operationsType = 'influence';
    operationsCountry = influenceTargets[0] || '';
    influencePoints = 1;
    influencePlacements = [];
    realignmentTargets = [];
    eventCountry = '';
    eventCountries = [];
    eventCountryAmounts = {};
    eventSourceAmounts = {};
    eventTargetAmounts = {};
    eventMode = 'south_africa';
    if (card.id === 16) eventMode = 'remove_us';
    eventChoiceValue = '';
    includeBonusOperations = false;
    bonusOperationsType = [47, 91, 96].includes(card.id) ? (card.id === 47 ? 'realignment' : 'coup') : 'influence';
    bonusOperationsCountry = '';
    bonusInfluencePoints = 1;
    bonusInfluencePlacements = [];
    bonusRealignmentTargets = [];
    tehranSelectedCardIds = [];
  }

  function controlledByAny(country) {
    const values = data.countries?.[country] || {};
    const threshold = countryInfo[country]?.stability || 0;
    return Math.abs((values.us || 0) - (values.ussr || 0)) >= threshold;
  }

  function controlledByFaction(country, side) {
    const values = data.countries?.[country] || {};
    const stability = countryInfo[country]?.stability || 0;
    const own = values[side] || 0;
    const opposing = values[side === 'us' ? 'ussr' : 'us'] || 0;
    return own - opposing >= stability;
  }

  function toggleEventCountry(country) {
    if (eventCountries.includes(country)) {
      eventCountries = eventCountries.filter((name) => name !== country);
      const amounts = { ...eventCountryAmounts };
      delete amounts[country];
      eventCountryAmounts = amounts;
    } else if (eventCountries.length < eventCountrySelectionLimit) {
      eventCountries = [...eventCountries, country];
      if (selectedCardId === 76) eventCountryAmounts = { ...eventCountryAmounts, [country]: 1 };
    }
  }

  function setUssuriAmount(country, amount) {
    eventCountryAmounts = { ...eventCountryAmounts, [country]: amount };
  }

  function setEventCountryAmount(country, amount) {
    eventCountryAmounts = { ...eventCountryAmounts, [country]: Number(amount) };
  }

  function setEventSourceAmount(country, amount) {
    eventSourceAmounts = { ...eventSourceAmounts, [country]: Number(amount) };
  }

  function setEventTargetAmount(country, amount) {
    eventTargetAmounts = { ...eventTargetAmounts, [country]: Number(amount) };
  }

  function buildEventChoices() {
    if (selectedCardId === 45) return { summit_defcon: Number(eventChoiceValue || 0) };
    if (selectedCardId === 47) return { junta: eventCountry };
    if (selectedCardId === 33) return { de_stalinization: { from: Object.fromEntries(Object.entries(eventSourceAmounts).filter(([, amount]) => Number(amount) > 0)), to: Object.fromEntries(Object.entries(eventTargetAmounts).filter(([, amount]) => Number(amount) > 0)) } };
    if (selectedCardId === 100) return { wargames: eventChoiceValue === 'end' };
    if (selectedCardId === 19 || selectedCardId === 22) return { [selectedEventKey]: eventCountry };
    if ([24, 36].includes(selectedCardId)) return { [selectedEventKey]: eventCountry };
    if (selectedCardId === 23) return { marshall_plan: eventCountries };
    if (selectedCardId === 16) {
      const choice = eventMode === 'remove_us'
        ? { mode: 'remove_us', countries: eventCountries }
        : { mode: 'add_ussr', distribution: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
      return { warsaw_pact_formed: choice };
    }
    if (selectedCardId === 76) {
      return ussuriRequiresPlacement
        ? { ussuri_river_skirmish: Object.fromEntries(eventCountries.map((name) => [name, Number(eventCountryAmounts[name])])) }
        : {};
    }
    if ([14, 29, 30, 63, 66].includes(selectedCardId)) return { [selectedEventKey]: eventCountries };
    if (selectedCardId === 28) return { suez_crisis: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 53) return { south_african_unrest: { mode: eventMode, ...(eventMode === 'adjacent' ? { adjacent: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) } : {}) } };
    if (selectedCardId === 70) return { oas_founded: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 88) return { marine_barracks_bombing: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 75) return { liberation_theology: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 74) return { [selectedEventKey]: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 7) {
      return { socialist_governments: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    }
    if (selectedCardId === 87) return { reformer: Object.fromEntries(Object.entries(eventCountryAmounts).filter(([, amount]) => Number(amount) > 0).map(([name, amount]) => [name, Number(amount)])) };
    if (selectedCardId === 99) return { pershing_ii_deployed: eventCountries };
    if (selectedCardId === 67) return { grain_sales: eventChoiceValue || 'return' };
    if (selectedCardId === 43) return eventChoiceValue ? { salt_negotiations: Number(eventChoiceValue) } : {};
    if ([49, 85].includes(selectedCardId)) return eventChoiceValue ? { [selectedEventKey]: Number(eventChoiceValue) } : {};
    if (selectedCardId === 77) return { ask_not_what: eventCountries.map(Number) };
    return JSON.parse(eventChoicesText || '{}');
  }

  function buildOperationsAction() {
    if (operationsType === 'space_race') return { type: 'space_race' };
    if (!operationsCountry || !operationTargets.includes(operationsCountry)) {
      throw new Error('Choose an available target for this Operations type.');
    }
    if (operationsType === 'influence') {
      if (influencePlacements.length) return { type: 'influence', placements: influencePlacements.filter((placement) => Number(placement.points) > 0) };
      return { type: 'influence', placements: [{ country: operationsCountry, points: Number(influencePoints) }] };
    }
    if (operationsType === 'realignment') {
      if (realignmentTargets.length) return { type: 'realignment', targets: realignmentTargets.map((country) => ({ country })) };
      return { type: 'realignment', targets: [{ country: operationsCountry }] };
    }
    return { type: 'coup', country: operationsCountry };
  }

  function buildBonusOperationsAction() {
    if (!bonusOperationsCountry || !bonusOperationsTargets.includes(bonusOperationsCountry)) {
      throw new Error('Choose a valid bonus Operations target.');
    }
    if ([47, 91, 96].includes(selectedCardId) && !['coup', 'realignment'].includes(bonusOperationsType)) {
      throw new Error('This event permits only coup or realignment bonus actions.');
    }
    if (selectedCardId === 91 && bonusOperationsType !== 'coup') {
      throw new Error('Ortega permits a coup only.');
    }
    if (selectedCardId === 90 && bonusOperationsType === 'coup') {
      throw new Error('Glasnost permits influence or realignment only.');
    }
    if (selectedCardId === 47 && !['Central America', 'South America'].includes(countryInfo[bonusOperationsCountry]?.region)) {
      throw new Error('Junta bonus targets Central or South America.');
    }
    if (selectedCardId === 91 && !(countryInfo['Nicaragua']?.adjacent_countries || []).includes(bonusOperationsCountry)) {
      throw new Error('Ortega bonus targets a country adjacent to Nicaragua.');
    }
    if (selectedCardId === 96 && countryInfo[bonusOperationsCountry]?.region !== 'Europe') {
      throw new Error('Tear Down This Wall bonus targets Europe.');
    }
    if (selectedCardId === 90 && !data.persistent_events?.reformer) throw new Error('Glasnost bonus requires The Reformer.');
    if (bonusOperationsType === 'influence') {
      const placements = [{ country: bonusOperationsCountry, points: Number(bonusInfluencePoints) }, ...bonusInfluencePlacements].filter((item) => Number(item.points) > 0);
      const total = placements.reduce((sum, item) => sum + Number(item.points || 0), 0);
      if (total > bonusOperationsBudget || placements.some((item) => !bonusOperationsTargets.includes(item.country) || !Number.isInteger(Number(item.points)) || Number(item.points) < 1)) throw new Error(`Bonus influence must use valid targets and no more than ${bonusOperationsBudget} Ops.`);
      return { type: 'influence', placements };
    }
    if (bonusOperationsType === 'realignment') {
      const targets = selectedCardId === 47 ? [bonusOperationsCountry] : [bonusOperationsCountry, ...bonusRealignmentTargets].filter(Boolean);
      const cap = selectedCardId === 47 ? 1 : bonusOperationsBudget;
      if (!targets.length || targets.length > cap || targets.some((country) => !bonusOperationsCountryOptions.includes(country))) throw new Error(`Bonus realignment allows at most ${cap} legal roll(s).`);
      return { type: 'realignment', targets: targets.map((country) => ({ country })) };
    }
    return { type: 'coup', country: bonusOperationsCountry };
  }

  function chooseMapTarget(country) {
    if (operationTargets.includes(country)) operationsCountry = country;
  }

  function submitCard() {
    if (!selectedTemplate) return;
    const move = { ...selectedTemplate, mode: selectedMode };
    try {
      if (selectedMode === 'event') {
        if (selectedTemplate.interactive_modes?.includes('event')) {
          move.interactive = true;
        } else {
          const choices = selectedEventKey ? buildEventChoices() : JSON.parse(eventChoicesText || '{}');
          if (Object.keys(choices).length) move.event_choices = choices;
          if ([49, 85].includes(selectedCardId) && eventChoiceValue) {
            const nestedChoices = JSON.parse(nestedEventChoicesText || '{}');
            if (!nestedChoices || typeof nestedChoices !== 'object' || Array.isArray(nestedChoices)) throw new Error('Nested event choices must be a JSON object.');
            move.event_choices = { ...(move.event_choices || {}), ...nestedChoices };
          }
          if (bonusOperationsEligible && includeBonusOperations) {
            move.event_choices = { ...(move.event_choices || {}), bonus_operations: buildBonusOperationsAction() };
          }
          if (selectedCardId === 46) move.chosen_defcon = Number(chosenDefcon);
        }
      } else {
        move.operations_action = buildOperationsAction();
      }
      emit(move);
    } catch (error) {
      formError = `Check the choice data: ${error.message}`;
    }
  }

  function submitStaged(move) {
    if (move.type === 'event_bonus' && move.decline === false) {
      try {
        emit({ ...move, operations_action: buildOperationsAction() });
      } catch (error) {
        formError = `Check the Operations action: ${error.message}`;
      }
      return;
    }
    if (move.type === 'card_operations') {
      try {
        emit({ ...move, operations_action: buildOperationsAction() });
      } catch (error) {
        formError = `Check the Operations action: ${error.message}`;
      }
      return;
    }
    emit(move);
  }

  function cardAsset(card) {
    return card?.card_face_asset ? `/api/v1/img/twilight-struggle/${card.card_face_asset}` : '';
  }

  function number(value) {
    return Number.isFinite(Number(value)) ? Number(value) : 0;
  }
</script>

<svelte:head>
  <title>Twilight Struggle · RBGG</title>
</svelte:head>

<div class="ts-shell">
  <header class="topbar">
    <div>
      <p class="eyebrow">THE COLD WAR · TURN {data.turn || 1}</p>
      <h1>Twilight Struggle</h1>
    </div>
    <div class="active-player" style={`--side-color:${COLOR[faction] || '#718096'}`}>
      <span class="status-dot"></span>
      <span>{factionName}</span>
      <small>{phase.replaceAll('_', ' ')}</small>
    </div>
  </header>

  <section class="tracks" aria-label="Game tracks">
    <article class="track vp"><span>Victory points</span><strong>{number(operations.victory_points) > 0 ? '+' : ''}{number(operations.victory_points)}</strong><small>US perspective</small></article>
    <article class="track defcon"><span>DEFCON</span><strong>{operations.defcon ?? '—'}</strong><small>1 means nuclear war</small></article>
    <article class="track"><span>Military operations</span><strong>US {operations.military_operations?.us ?? 0} <i>·</i> USSR {operations.military_operations?.ussr ?? 0}</strong><small>Current turn</small></article>
    <article class="track"><span>Space race</span><strong>US {operations.space_race?.us ?? 0} <i>·</i> USSR {operations.space_race?.ussr ?? 0}</strong><small>Track position</small></article>
  </section>

  {#if data.pending_event}
    <aside class="pending" aria-live="polite">
      <strong>Decision required · Card {data.pending_event.card_id}</strong>
      <span>{data.pending_event.stage?.replaceAll('_', ' ')} · Responding player: {data.pending_event.responding_player}</span>
    </aside>
  {/if}

  <main class="layout">
    <section class="board-panel panel">
      <div class="section-heading">
        <div><p class="eyebrow">GLOBAL INFLUENCE</p><h2>World board</h2></div>
        <div class="map-tools" aria-label="Map zoom controls">
          <button type="button" aria-label="Zoom out" title="Zoom out" disabled={mapZoom <= 1} on:click={() => mapZoom = Math.max(1, +(mapZoom - 0.25).toFixed(2))}>−</button>
          <span>{Math.round(mapZoom * 100)}%</span>
          <button type="button" aria-label="Zoom in" title="Zoom in" disabled={mapZoom >= 2.5} on:click={() => mapZoom = Math.min(2.5, +(mapZoom + 0.25).toFixed(2))}>+</button>
          <button type="button" class="reset-zoom" disabled={mapZoom === 1} on:click={() => mapZoom = 1}>Reset</button>
        </div>
      </div>
      {#if Object.keys(data.countries || {}).length}
        <div class="map-scroll">
          <div class="world-map" style={`width:${mapZoom * 100}%`}>
            <img class="map-art" src="/api/v1/img/twilight-struggle/TS%20Map-11.jpg" alt="Twilight Struggle world map" />
            {#each Object.entries(data.countries) as [country, influence]}
              {@const position = mapPositions[country]}
              {#if position && ((influence.us || 0) > 0 || (influence.ussr || 0) > 0)}
                <button
                  class="map-space"
                  class:map-space-selected={operationsCountry === country}
                  style={`left:${position.x / 5100 * 100}%;top:${position.y / 3300 * 100}%`}
                  aria-label={`${country}: US ${influence.us || 0}, USSR ${influence.ussr || 0}. Select as Operations target.`}
                  title={`${country} · US ${influence.us || 0} / USSR ${influence.ussr || 0}`}
                    on:click={() => chooseMapTarget(country)}
                >
                  <span class="us-token">{influence.us || 0}</span><span class="ussr-token">{influence.ussr || 0}</span>
                </button>
              {/if}
            {/each}
          </div>
        </div>
      {:else}
        <p class="empty">Waiting for the game state…</p>
      {/if}
    </section>

    <section class="panel hand-panel">
      <div class="section-heading"><div><p class="eyebrow">PRIVATE TO YOU</p><h2>Your hand</h2></div><span class="country-count">{hand.length} cards</span></div>
      {#if hand.length}
        <div class="hand-list">
          {#each hand as card}
            {@const playable = cardMoves.some((move) => move.card_id === card.id)}
            <button class="hand-card" class:selected={selectedCardId === card.id} class:playable={playable} disabled={!playable || !canChoose} aria-label={`${card.name}, ${card.operations} Operations${card.scoring ? ', scoring card' : ''}${playable ? ', playable' : ', not currently playable'}`} title={`${card.name} · ${card.operations} Ops · ${card.alignment}`} on:click={() => selectCard(card)}>
              {#if cardAsset(card)}<img src={cardAsset(card)} alt={card.name} />{/if}
              <span class="card-caption"><strong>{card.name}</strong><small>{card.operations} Ops · {card.alignment}{card.scoring ? ' · Scoring' : ''}</small></span>
              {#if playable}<em>Playable</em>{/if}
            </button>
          {/each}
        </div>
      {:else}
        <p class="empty">No hand is visible to this player.</p>
      {/if}
    </section>

    <aside class="side-column">
      <section class="panel move-panel">
        <div class="section-heading"><div><p class="eyebrow">YOUR DECISION</p><h2>Available moves</h2></div></div>
        {#if stagedMoves.length}
          <p class="instruction">Choose an option to resolve this card.</p>
          <div class="move-options">
            {#each stagedMoves as move, index}
              {#if move.decision !== 'discard_revealed_cards'}
              <button class="choice-button" disabled={!canChoose} on:click={() => submitStaged(move)}>
                <span>{move.decision || move.type.replaceAll('_', ' ')}</span>
                {#if move.country}<small>{move.country}</small>{/if}
                {#if move.card_id}<small>Card {move.card_id}</small>{/if}
                {#if move.countries}<small>{move.countries.join(' · ')}</small>{/if}
                {#if move.region}<small>{move.region}</small>{/if}
              </button>
              {/if}
              {#if move.decision === 'discard_revealed_cards' && Array.isArray(move.revealed_cards)}
                <div class="panel" aria-label="Our Man in Tehran revealed cards">
                  <p class="instruction">The United States privately reviews the revealed cards and chooses any subset to discard.</p>
                  <div class="country-choices" role="group" aria-label="Select Tehran discards">
                    {#each move.revealed_cards as card}
                      <label class="check-row"><input type="checkbox" bind:group={tehranSelectedCardIds} value={card.id} /> {card.name}</label>
                    {/each}
                  </div>
                  <button class="primary-button" disabled={!canChoose} on:click={submitTehranDiscards}>Confirm discards</button>
                </div>
              {/if}
            {/each}
          </div>
          {#if hasStagedCardOperations || hasStagedBonusOperations}
            <div class="ops-builder">
              <label class="field-label" for="staged-ops-type">Operations</label>
              <select id="staged-ops-type" bind:value={operationsType} on:change={() => { influencePlacements = []; realignmentTargets = []; }}>
                <option value="influence">Place influence</option>
                {#if hasStagedBonusOperations}<option value="coup">Coup</option>{/if}
                <option value="realignment">Realignment</option>
              </select>
              {#if operationsType !== 'space_race'}
                <label class="field-label" for="staged-ops-country">Target country</label>
                <select id="staged-ops-country" bind:value={operationsCountry}>
                  {#each operationTargets as country}<option value={country}>{country}</option>{/each}
                </select>
              {/if}
              {#if operationsType === 'influence'}
                <label class="field-label" for="staged-influence-points">Influence points</label>
                <input id="staged-influence-points" type="number" min="1" max="4" bind:value={influencePoints} />
                {#if hasStagedCardOperations && operationsBudget > 1}
                  <button type="button" on:click={() => influencePlacements = [...influencePlacements, { country: operationTargets[0] || '', points: 1 }]}>Add another placement</button>
                  {#each influencePlacements as placement, index}
                    <label class="field-label" for="staged-placement-country-{index}">Placement {index + 1}
                      <select id="staged-placement-country-{index}" bind:value={placement.country}>{#each operationTargets as country}<option value={country}>{country}</option>{/each}</select>
                      <input aria-label="Staged placement {index + 1} points" type="number" min="1" max={operationsBudget} bind:value={placement.points} />
                    </label>
                  {/each}
                {/if}
              {:else if operationsType === 'realignment' && hasStagedCardOperations && operationsBudget > 1}
                <button type="button" on:click={() => realignmentTargets = [...realignmentTargets, operationTargets[0] || '']}>Add another realignment</button>
                {#each realignmentTargets as target, index}
                  <label class="field-label" for="staged-realignment-target-{index}">Realignment {index + 1}
                    <select id="staged-realignment-target-{index}" bind:value={realignmentTargets[index]}>{#each operationTargets as country}<option value={country}>{country}</option>{/each}</select>
                  </label>
                {/each}
              {/if}
              <p class="hint">Dice are generated by the server. The game engine checks target legality and the Operations budget.</p>
            </div>
          {/if}
        {:else if phase === 'headline'}
          <p class="instruction">Select a legal headline. Selections remain hidden until both players commit.</p>
          <div class="move-options">
            {#each moves.filter((move) => move.type === 'headline') as move}
              <button class="choice-button" disabled={!canChoose} on:click={() => emit(move)}>
                <span>{hand.find((card) => card.id === move.card_id)?.name || `Card ${move.card_id}`}</span><small>Commit headline</small>
              </button>
            {/each}
          </div>
          {#if moves.some((move) => move.type === 'reveal_headlines')}
            <button class="primary-button" disabled={!canChoose} on:click={() => emit(moves.find((move) => move.type === 'reveal_headlines'))}>Reveal headlines</button>
          {/if}
        {:else if cardMoves.length}
          <p class="instruction">Choose a card from your hand, then select its event or Operations mode.</p>
          {#if selectedTemplate}
            <div class="selected-card"><strong>{selectedCard?.name || `Card ${selectedCardId}`}</strong><span>{selectedCard?.operations} Ops · {selectedCard?.alignment}</span></div>
            <div class="mode-tabs">
              {#each selectedTemplate.modes || ['event', 'operations'] as mode}
                <button class:active={selectedMode === mode} on:click={() => selectedMode = mode}>{mode}</button>
              {/each}
            </div>
            {#if selectedMode === 'event' && selectedTemplate.interactive_modes?.includes('event')}
              <p class="hint">{selectedCardId === 108 ? 'Commit the event to draw up to five cards; the US will privately choose discards after the reveal.' : 'This event pauses for the designated player to make a private, legal choice.'}</p>
            {:else if selectedMode === 'event'}
              {#if selectedEventKey}
                {#if selectedCardId === 45}
                  <label class="field-label" for="event-choice-value">Summit DEFCON choice</label>
                  <select id="event-choice-value" bind:value={eventChoiceValue}><option value="0">No change</option><option value="1">Improve DEFCON by 1</option><option value="-1">Reduce DEFCON by 1</option></select>
                {:else if selectedCardId === 108}
                  <p class="hint">Commit the event to reveal up to five cards privately to the US for the discard decision.</p>
                  <label class="field-label" for="event-mode">Placement choice</label>
                  <select id="event-mode" bind:value={eventMode} on:change={() => { eventCountries = []; eventCountryAmounts = {}; }}><option value="south_africa">2 influence in South Africa</option><option value="adjacent">1 in South Africa, 2 adjacent</option></select>
                  {#if eventMode === 'adjacent'}
                    <p class="hint">Allocate exactly 2 additional USSR influence among countries adjacent to South Africa.</p>
                    <div class="country-choices" role="group" aria-label="South African Unrest adjacent influence allocation">
                      {#each eventCountryOptions as country}
                        <label class="field-label" for="south-africa-{country}">{country}
                          <select id="south-africa-{country}" aria-label="USSR influence placed in {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                            <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                          </select>
                        </label>
                      {/each}
                    </div>
                    <p class="hint">Adjacent allocation: {Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0)} / 2</p>
                  {/if}
                {:else if selectedCardId === 76}
                  {#if data.china_card?.owner === 'us'}
                    <p class="hint">The US holds The China Card: place exactly 4 influence in Asia, with 1 or 2 per country.</p>
                    <div class="country-choices" role="group" aria-label="Ussuri influence choices">
                      {#each eventCountries as country}
                        <label class="field-label">{country}
                          <button type="button" aria-label="1 influence in {country}" class:choice-selected={Number(eventCountryAmounts[country]) === 1} on:click={() => setUssuriAmount(country, 1)}>1 influence</button>
                          <button type="button" aria-label="2 influence in {country}" class:choice-selected={Number(eventCountryAmounts[country]) === 2} on:click={() => setUssuriAmount(country, 2)}>2 influence</button>
                        </label>
                      {/each}
                      {#if !eventCountries.length}
                        {#each eventCountryOptions as country}
                          <button type="button" aria-label="Add {country}" on:click={() => toggleEventCountry(country)}>{country}</button>
                        {/each}
                      {:else}
                        {#each eventCountryOptions.filter((name) => !eventCountries.includes(name)) as country}
                          <button type="button" aria-label="Add {country}" on:click={() => toggleEventCountry(country)}>{country}</button>
                        {/each}
                      {/if}
                    </div>
                    <p class="hint">Allocated: {eventCountries.reduce((total, name) => total + Number(eventCountryAmounts[name] || 0), 0)} / 4</p>
                  {:else if data.china_card?.owner === 'ussr'}
                    <p class="hint">The USSR holds The China Card; this event transfers it to the US without a placement choice.</p>
                  {:else}
                    <p class="hint">The China Card is not held by either faction; the event cannot resolve.</p>
                  {/if}
                {:else if selectedCardId === 70}
                  <p class="hint">Allocate exactly 2 US influence across Central and South America.</p>
                  <div class="country-choices" role="group" aria-label="OAS influence allocation">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="oas-{country}">{country}
                        <select id="oas-{country}" aria-label="OAS influence in {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {oasInfluenceTotal} / 2</p>
                {:else if selectedCardId === 28}
                  <p class="hint">Remove exactly 4 US influence from France, the U.K., and Israel; at most 2 per country.</p>
                  <div class="country-choices" role="group" aria-label="Suez Crisis US influence removal allocation">
                    {#each ['France', 'U.K.', 'Israel'].filter((name) => Number(data.countries[name]?.us || 0) > 0) as country}
                      <label class="field-label" for="suez-{country}">{country} · US {data.countries[country]?.us || 0}
                        <select id="suez-{country}" aria-label="US influence removed from {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          {#each [0, 1, 2].filter((amount) => amount <= Math.min(2, Number(data.countries[country]?.us || 0))) as amount}
                            <option value={amount}>{amount} influence</option>
                          {/each}
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0)} / 4</p>
                {:else if selectedCardId === 7}
                  <p class="hint">Remove exactly 3 US influence from Western Europe, with no more than 2 from any one country.</p>
                  <div class="country-choices" role="group" aria-label="Socialist Governments influence removal allocation">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="socialist-{country}">{country} · US {data.countries[country]?.us || 0}
                        <select id="socialist-{country}" aria-label="US influence removed from {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          {#each [0, 1, 2].filter((amount) => amount <= Number(data.countries[country]?.us || 0)) as amount}
                            <option value={amount}>{amount} influence</option>
                          {/each}
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0)} / 3</p>
                {:else if selectedCardId === 16 && eventMode === 'add_ussr'}
                  <p class="hint">Place exactly 5 USSR influence in Eastern Europe; no more than 2 per country.</p>
                  <div class="country-choices" role="group" aria-label="Warsaw Pact USSR placement allocation">
                    {#each ['E. Germany', 'Poland', 'Czechoslovakia', 'Hungary', 'Romania', 'Bulgaria'] as country}
                      <label class="field-label" for="warsaw-{country}">{country}
                        <select id="warsaw-{country}" aria-label="USSR influence placed in {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0)} / 5</p>
                {:else if selectedCardId === 74}
                  <p class="hint">Optionally remove up to 4 USSR influence outside Europe, at most 2 per country.</p>
                  <div class="country-choices" role="group" aria-label="Voice of America influence removal allocation">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="voice-{country}">{country} · USSR {data.countries[country]?.ussr || 0}
                        <select id="voice-{country}" aria-label="USSR influence removed from {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          {#each [0, 1, 2].filter((amount) => amount <= Math.min(2, Number(data.countries[country]?.ussr || 0))) as amount}
                            <option value={amount}>{amount} influence</option>
                          {/each}
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Removed: {voiceRemovalTotal} / 4</p>
                {:else if selectedCardId === 87}
                  {@const reformerTotal = Number(operations.victory_points) < 0 ? 6 : 4}
                  <p class="hint">Place exactly {reformerTotal} USSR influence in Europe, at most 2 per country.</p>
                  <div class="country-choices" role="group" aria-label="Reformer influence allocation">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="reformer-{country}">{country}
                        <select id="reformer-{country}" aria-label="USSR influence placed in {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {Object.values(eventCountryAmounts).reduce((total, amount) => total + (Number(amount) || 0), 0)} / {reformerTotal}</p>
                {:else if selectedCardId === 45}
                  <label class="field-label" for="event-choice-value">Summit DEFCON choice</label>
                  <select id="event-choice-value" bind:value={eventChoiceValue}><option value="0">No change</option><option value="1">Improve DEFCON by 1</option><option value="-1">Reduce DEFCON by 1</option></select>
                {:else if selectedCardId === 47}
                  <p class="hint">Choose a Central or South American country for Junta.</p>
                  <label class="field-label" for="event-country">Choose a country</label>
                  <select id="event-country" bind:value={eventCountry}><option value="" disabled>Select a country</option>{#each eventCountryOptions as country}<option value={country}>{country}</option>{/each}</select>
                {:else if selectedCardId === 108}
                  <p class="hint">Commit the event to reveal up to five cards privately to the US for the discard decision.</p>
                {:else if selectedCardId === 33}
                  <p class="hint">Move up to 4 USSR influence. Source and destination totals must match; no destination may receive more than 2.</p>
                  <div class="country-choices" role="group" aria-label="De-Stalinization source allocation">
                    <strong>Remove from</strong>
                    {#each countryNames.filter((country) => Number(data.countries[country]?.ussr || 0) > 0) as country}
                      <label class="field-label" for="dst-from-{country}">{country} · USSR {data.countries[country]?.ussr || 0}
                        <select id="dst-from-{country}" aria-label="USSR influence removed from {country}" value={eventSourceAmounts[country] ?? 0} on:change={(event) => setEventSourceAmount(country, event.currentTarget.value)}>
                          {#each Array.from({ length: Math.min(4, Number(data.countries[country]?.ussr || 0)) + 1 }, (_, amount) => amount) as amount}
                            <option value={amount}>{amount} influence</option>
                          {/each}
                        </select>
                      </label>
                    {/each}
                  </div>
                  <div class="country-choices" role="group" aria-label="De-Stalinization destination allocation">
                    <strong>Place in</strong>
                    {#each countryNames.filter((country) => !controlledByFaction(country, 'us')) as country}
                      <label class="field-label" for="dst-to-{country}">{country}
                        <select id="dst-to-{country}" aria-label="USSR influence placed in {country}" value={eventTargetAmounts[country] ?? 0} on:change={(event) => setEventTargetAmount(country, event.currentTarget.value)}>
                          <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Moved: {deStalinizationFromTotal} / 4 · Placed: {deStalinizationToTotal}</p>
                {:else if selectedCardId === 88}
                  <p class="hint">Lebanon is handled automatically. Optionally remove up to 2 additional US influence from the Middle East.</p>
                  <div class="country-choices" role="group" aria-label="Marine Barracks additional removals">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="marine-{country}">{country}
                        <select id="marine-{country}" aria-label="Additional US influence removed from {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          {#each [0, 1, 2].filter((amount) => amount <= Math.min(2, Number(data.countries[country]?.us || 0))) as amount}
                            <option value={amount}>{amount} influence</option>
                          {/each}
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Additional influence selected: {marineRemovalTotal} / 2</p>
                {:else if selectedCardId === 75}
                  <p class="hint">Allocate exactly 3 USSR influence in Central America, with no more than 2 in any one country.</p>
                  <div class="country-choices" role="group" aria-label="Liberation Theology influence allocation">
                    {#each eventCountryOptions as country}
                      <label class="field-label" for="liberation-{country}">{country}
                        <select id="liberation-{country}" aria-label="USSR influence placed in {country}" value={eventCountryAmounts[country] ?? 0} on:change={(event) => setEventCountryAmount(country, event.currentTarget.value)}>
                          <option value={0}>0 influence</option><option value={1}>1 influence</option><option value={2}>2 influence</option>
                        </select>
                      </label>
                    {/each}
                  </div>
                  <p class="hint">Allocated: {liberationInfluenceTotal} / 3</p>
                {:else if [43, 49, 67, 85].includes(selectedCardId)}
                  {#if selectedCardId === 67}
                    <label class="field-label" for="event-choice-value">Grain Sales choice</label>
                    <select id="event-choice-value" bind:value={eventChoiceValue}><option value="return">Return the card; take Operations</option><option value="play">Play the drawn event; skip Operations</option></select>
                  {:else}
                    <label class="field-label" for="event-choice-value">Choose a card</label>
                    <select id="event-choice-value" bind:value={eventChoiceValue}><option value="">{selectedCardId === 49 ? 'Use default card selection' : 'Select a discard-pile card'}</option>{#each eventChoiceOptions as cardId}<option value={cardId}>{(selectedCardId === 49 ? data.revealed_hands?.[faction === 'us' ? 'ussr' : 'us'] : data.discard_pile)?.find((card) => String(card.id) === cardId)?.name || `Card ${cardId}`}</option>{/each}</select>
                  {/if}
                {:else}
                  <label class="field-label" for="event-country">Choose a country</label>
                  <select id="event-country" bind:value={eventCountry}><option value="" disabled>Select a country</option>{#each eventCountryOptions as country}<option value={country}>{country}</option>{/each}</select>
                {/if}
              {:else}
                <label class="field-label" for="event-choices">Advanced event choices (JSON)</label>
                <textarea id="event-choices" bind:value={eventChoicesText} rows="3" spellcheck="false"></textarea>
              {/if}
                {#if bonusOperationsAvailable}
                <label class="check-row"><input type="checkbox" bind:checked={includeBonusOperations} /> Add optional bonus Operations</label>
                {#if includeBonusOperations}
                    <p class="hint">Bonus budget: {bonusOperationsBudget} Ops. {#if selectedCardId === 90}<strong>Requires The Reformer.</strong>{/if} Regional free actions bypass geographic DEFCON bans; other restrictions still apply.</p>
                  <label class="field-label" for="bonus-ops-type">Bonus action</label>
                    <select id="bonus-ops-type" bind:value={bonusOperationsType} on:change={() => { bonusOperationsCountry = ''; bonusInfluencePlacements = []; bonusRealignmentTargets = []; }}>
                    {#if ![47, 91, 96, 90].includes(selectedCardId)}<option value="influence">Place influence</option>{/if}
                    {#if selectedCardId !== 91}<option value="realignment">Realignment</option>{/if}
                    {#if selectedCardId !== 90}<option value="coup">Coup</option>{/if}
                  </select>
                  <label class="field-label" for="bonus-ops-country">Bonus target country</label>
                  <select id="bonus-ops-country" bind:value={bonusOperationsCountry}>
                    <option value="" disabled>Select a country</option>
                    {#each bonusOperationsCountryOptions as country}<option value={country}>{country}</option>{/each}
                  </select>
                    {#if bonusOperationsType === 'influence'}
                      <label class="field-label" for="bonus-influence-points">Influence points</label>
                      <input id="bonus-influence-points" type="number" min="1" max={bonusOperationsBudget} bind:value={bonusInfluencePoints} />
                      {#if bonusOperationsBudget > 1}<button type="button" on:click={() => bonusInfluencePlacements = [...bonusInfluencePlacements, { country: bonusOperationsCountryOptions[0] || '', points: 1 }]}>Add another bonus placement</button>{/if}
                      {#each bonusInfluencePlacements as placement, index}
                        <label class="field-label" for="bonus-placement-country-{index}">Bonus placement {index + 1}
                          <select id="bonus-placement-country-{index}" bind:value={placement.country}>{#each bonusOperationsTargets as country}<option value={country}>{country}</option>{/each}</select>
                          <input aria-label="Bonus placement {index + 1} points" type="number" min="1" max={bonusOperationsBudget} bind:value={placement.points} />
                        </label>
                      {/each}
                    {:else if bonusOperationsType === 'realignment'}
                      <p class="hint">{selectedCardId === 47 ? 'Junta grants one realignment roll.' : `Up to ${bonusOperationsBudget} realignment rolls.`}</p>
                      {#if selectedCardId !== 47 && bonusOperationsBudget > 1}<button type="button" on:click={() => bonusRealignmentTargets = [...bonusRealignmentTargets, bonusOperationsCountryOptions[0] || '']}>Add another realignment roll</button>{/if}
                      {#each bonusRealignmentTargets as target, index}
                        <label class="field-label" for="bonus-realignment-target-{index}">Bonus roll {index + 1}
                          <select id="bonus-realignment-target-{index}" bind:value={bonusRealignmentTargets[index]}>{#each bonusOperationsCountryOptions as country}<option value={country}>{country}</option>{/each}</select>
                        </label>
                      {/each}
                    {/if}
                {/if}
              {/if}
              {#if selectedCardId === 46}
                <label class="field-label" for="chosen-defcon">Choose DEFCON</label>
                <select id="chosen-defcon" bind:value={chosenDefcon}>{#each [1,2,3,4,5] as level}<option value={level}>{level}</option>{/each}</select>
              {/if}
                {#if [49, 85].includes(selectedCardId) && eventChoiceValue}
                  <label class="field-label" for="nested-event-choices">Selected card event choices (JSON)</label>
                  <textarea id="nested-event-choices" bind:value={nestedEventChoicesText} rows="3" spellcheck="false" placeholder="No additional event choices"></textarea>
                  <p class="hint">Use the selected card's event-choice key here if its event requires an additional choice. The backend validates the nested choice.</p>
                {/if}
            {:else}
              <div class="ops-builder">
                <label class="field-label" for="operations-type">Operations</label>
                <select id="operations-type" bind:value={operationsType}>
                  <option value="influence">Place influence</option><option value="coup">Coup</option>
                  <option value="realignment">Realignment</option><option value="space_race">Space Race</option>
                </select>
                {#if operationsType !== 'space_race'}
                  <label class="field-label" for="operations-country">Target country</label>
                  <select id="operations-country" bind:value={operationsCountry}>
                    {#each operationTargets as country}<option value={country}>{country}</option>{/each}
                  </select>
                {/if}
                {#if operationsType === 'influence'}
                  <label class="field-label" for="influence-points">Influence points</label>
                  <input id="influence-points" type="number" min="1" max="4" bind:value={influencePoints} />
                  {#if selectedMode === 'operations' && operationsBudget > 1}
                    <button type="button" on:click={() => influencePlacements = [...influencePlacements, { country: operationTargets[0] || '', points: 1 }]}>Add another placement</button>
                    {#each influencePlacements as placement, index}
                      <label class="field-label" for="placement-country-{index}">Placement {index + 1}
                        <select id="placement-country-{index}" bind:value={placement.country}>{#each operationTargets as country}<option value={country}>{country}</option>{/each}</select>
                        <input aria-label="Placement {index + 1} points" type="number" min="1" max={operationsBudget} bind:value={placement.points} />
                      </label>
                    {/each}
                  {/if}
                {:else if operationsType === 'realignment' && selectedMode === 'operations' && operationsBudget > 1}
                  <button type="button" on:click={() => realignmentTargets = [...realignmentTargets, operationTargets[0] || '']}>Add another realignment</button>
                  {#each realignmentTargets as target, index}
                    <label class="field-label" for="realignment-target-{index}">Realignment {index + 1}
                      <select id="realignment-target-{index}" bind:value={realignmentTargets[index]}>{#each operationTargets as country}<option value={country}>{country}</option>{/each}</select>
                    </label>
                  {/each}
                {/if}
                <p class="hint">Dice are generated by the server. The game engine checks target legality and the Operations budget.</p>
              </div>
              <label class="check-row"><input type="checkbox" bind:checked={selectedTemplate.trigger_own_event} /> Trigger my aligned event when available</label>
            {/if}
            <button class="primary-button" disabled={!canChoose || (selectedMode === 'event' && selectedEventKey && !eventSelectionReady)} on:click={submitCard}>Play card</button>
            <button class="text-button" on:click={() => selectedCardId = null}>Cancel selection</button>
          {:else}
            <p class="empty">Select one of your held cards below.</p>
          {/if}
        {:else if moves.length}
          <p class="instruction">The backend's legal moves are shown here; select one to continue.</p>
          <div class="move-options">
            {#each moves as move, index}
              <button class="choice-button" disabled={!canChoose} on:click={() => emit(move)}>
                <span>{move.type.replaceAll('_', ' ')}</span><small>{move.country || move.card_id || move.decision || move.move_id}</small>
              </button>
            {/each}
          </div>
        {:else}
          <p class="empty">No legal moves are available for this view.</p>
        {/if}
        {#if formError}<p class="form-error" role="alert">{formError}</p>{/if}
      </section>

    </aside>
  </main>

  <footer class="disclaimer">Development UI · only moves exposed by the game engine are submitted. Unimplemented choice flows may require entering event-choice JSON.</footer>
</div>

<style>
  :global(body) { margin: 0; background: #101923; color: #edf2f7; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
  .ts-shell { width:100%; box-sizing:border-box; margin:0; padding:clamp(.5rem, 1.25vw, 1.25rem); }
  .topbar, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
  .topbar { margin-bottom: 1.6rem; }
  h1, h2, p { margin: 0; }
  h1 { font-family: Georgia, serif; font-size: clamp(1.8rem, 4vw, 3rem); letter-spacing: -.04em; }
  h2 { font-family: Georgia, serif; font-size: 1.35rem; }
  .eyebrow { color: #d8b46b; font-size: .66rem; font-weight: 800; letter-spacing: .16em; margin-bottom: .38rem; text-transform: uppercase; }
  .active-player { display: grid; grid-template-columns: 10px auto; gap: .15rem .55rem; align-items: center; border: 1px solid #334456; border-radius: 99px; padding: .6rem .9rem; font-weight: 700; }
  .active-player small { grid-column: 2; color: #a8b6c5; font-size: .7rem; text-transform: capitalize; }
  .status-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--side-color); box-shadow: 0 0 12px var(--side-color); }
  .tracks { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; margin-bottom: 1rem; }
  .track, .panel { border: 1px solid #2b3b4b; border-radius: 14px; background: #172330; }
  .track { min-height: 90px; padding: .9rem 1rem; display: flex; flex-direction: column; justify-content: center; gap: .28rem; }
  .track span, .track small { color: #9eafbe; font-size: .74rem; }
  .track strong { font-size: 1.3rem; }
  .track i { color: #607184; font-style: normal; padding: 0 .3rem; }
  .vp strong { color: #e6c87c; }
  .defcon strong { color: #f18477; }
  .pending { display:flex; flex-wrap:wrap; justify-content:space-between; gap:.5rem; background:#3a3021; color:#f5dfac; border:1px solid #82683b; padding:.75rem 1rem; border-radius:10px; margin:0 0 1rem; }
  .pending span { color:#dcc99d; font-size:.85rem; }
  .layout { display:grid; grid-template-columns:minmax(0, 1fr); align-items:start; gap:.8rem; }
  .panel { padding:1rem; min-width:0; }
  .board-panel { width:100%; box-sizing:border-box; }
  .side-column { display:grid; gap:1rem; }
  .country-count { color:#a9b7c4; font-size:.78rem; }
  .map-tools { display:flex; align-items:center; gap:.45rem; color:#d5e0e8; font-size:.8rem; }
  .map-tools button { min-width:2.2rem; height:2rem; border:1px solid #46596a; border-radius:7px; background:#1c2b38; color:#fff; font-size:1.15rem; }
  .map-tools .reset-zoom { min-width:auto; padding:0 .55rem; font-size:.75rem; }
  .map-scroll { overflow:auto; max-height:70vh; margin-top:.7rem; border:1px solid #344657; border-radius:8px; background:#101820; }
  .world-map { position:relative; min-width:100%; aspect-ratio:5100 / 3300; overflow:hidden; }
  .map-art { position:absolute; inset:0; width:100%; height:100%; object-fit:fill; }
  .map-space { position:absolute; z-index:1; display:flex; gap:1px; align-items:center; justify-content:center; transform:translate(-50%,-50%); min-width:25px; min-height:17px; padding:1px 2px; border:1px solid #17202b; border-radius:5px; background:rgba(13,23,33,.86); box-shadow:0 1px 4px #0009; cursor:pointer; }
  .map-space:hover, .map-space-selected { z-index:2; outline:2px solid #f0cb75; }
  .map-space .us-token, .map-space .ussr-token { display:grid; place-items:center; min-width:11px; height:13px; padding:0 1px; color:#fff; font-size:9px; line-height:1; font-weight:800; }
  .us-token { background:#2878c7; }.ussr-token { background:#c84b4b; }
  .instruction, .empty, .hint { color:#aebbc7; font-size:.84rem; line-height:1.5; margin:.8rem 0; }
  .move-options { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.5rem; max-height:340px; overflow:auto; margin:.8rem 0; }
  button, select, textarea { font:inherit; }
  button { cursor:pointer; }
  button:disabled { cursor:not-allowed; opacity:.5; }
  .choice-button { display:flex; flex-direction:column; gap:.22rem; align-items:flex-start; min-width:0; padding:.7rem; border:1px solid #34485a; border-radius:9px; background:#1c2b38; color:#eff4f8; text-align:left; }
  .choice-button:hover:not(:disabled), .hand-card:hover:not(:disabled) { border-color:#d5b366; background:#26394a; }
  .choice-button span { font-weight:700; text-transform:capitalize; }.choice-button small { color:#aab8c5; font-size:.72rem; }
  .field-label { display:block; color:#c4d0db; font-size:.77rem; font-weight:700; margin:.65rem 0 .3rem; }
  textarea, select, input[type="number"] { box-sizing:border-box; width:100%; border:1px solid #3b4c5b; border-radius:8px; background:#0e1821; color:#edf2f7; padding:.65rem; }
  textarea { resize:vertical; font: .76rem ui-monospace, Consolas, monospace; }
  .country-choices { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:.35rem; max-height:190px; overflow:auto; padding:.35rem 0; }
  .country-choices button { padding:.45rem .55rem; border:1px solid #3b4c5b; border-radius:7px; background:#111c26; color:#dce6ee; text-align:left; font-size:.75rem; }
  .country-choices button.choice-selected { border-color:#d5b366; background:#3a3325; color:#ffe3a0; }
  .country-choices button:focus-visible { outline:2px solid #e6c77f; outline-offset:1px; }
  .selected-card { display:flex; justify-content:space-between; gap:.5rem; padding:.75rem; margin:.8rem 0 .4rem; border-radius:8px; background:#253543; }
  .selected-card span { color:#aebdca; font-size:.76rem; }
  .mode-tabs { display:flex; gap:.4rem; margin:.6rem 0; }.mode-tabs button { flex:1; border:1px solid #43566a; background:#101b25; color:#cad5de; border-radius:7px; padding:.5rem; text-transform:capitalize; }.mode-tabs button.active { border-color:#d5b366; color:#f4d58a; }
  .primary-button { width:100%; margin-top:.75rem; padding:.75rem; border:0; border-radius:8px; background:#d1ad62; color:#1b2026; font-weight:800; }
  .primary-button:hover:not(:disabled) { background:#e6c77f; }
  .text-button { display:block; margin:.55rem auto 0; border:0; background:none; color:#aebbc7; font-size:.78rem; }
  .check-row { display:flex; gap:.5rem; align-items:center; color:#bfccd8; font-size:.78rem; margin:.6rem 0; }
  .form-error { color:#ffaaa0; margin-top:.65rem; font-size:.8rem; }
  .hand-list { display:flex; gap:.7rem; overflow-x:auto; padding:.8rem .15rem .65rem; }
  .hand-card { position:relative; flex:0 0 clamp(116px, 12vw, 170px); display:flex; flex-direction:column; gap:.35rem; overflow:hidden; padding:0; text-align:left; border:2px solid #304252; border-radius:8px; background:#101820; color:#eef2f5; }
  .hand-card img { display:block; width:100%; aspect-ratio:2 / 3; object-fit:cover; border-radius:5px; }
  .hand-card .card-caption { display:grid; gap:.2rem; padding:.3rem .4rem .45rem; }
  .hand-card strong { overflow:hidden; font-size:.68rem; white-space:nowrap; text-overflow:ellipsis; }
  .hand-card small { color:#9eafbe; font-size:.62rem; }
  .hand-card em { position:absolute; top:.35rem; right:.35rem; padding:.2rem .35rem; border-radius:4px; background:#132536e8; color:#f3d88f; font-size:.62rem; font-style:normal; font-weight:800; }
  .hand-card.playable { border-color:#71899c; }.hand-card.selected { border-color:#f0cd76; box-shadow:0 0 0 2px #f0cd7666; transform:translateY(-3px); }
  .disclaimer { color:#8293a2; font-size:.72rem; padding:1.2rem .2rem .2rem; }
  @media(max-width:850px) { .tracks { grid-template-columns:repeat(2,minmax(0,1fr)); }.map-scroll { max-height:60vh; }.panel { padding:.7rem; } }
  @media(max-width:480px) { .topbar { align-items:flex-start; flex-direction:column; }.tracks { gap:.45rem; }.track { padding:.7rem; } }
</style>
