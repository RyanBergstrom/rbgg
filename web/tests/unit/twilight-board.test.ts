import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import TwilightStruggleBoard from '../../src/lib/components/games/twilight_struggle/TwilightStruggleBoard.svelte';
import TwilightBoardEventCapture from '../fixtures/TwilightBoardEventCapture.svelte';

const mapPositions = { France: { x: 2500, y: 1200 } };
const countryInfo = {
  France: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  'U.K.': { region: 'Europe', stability: 5, battleground: true, adjacent_countries: ['France', 'Norway'] },
  Israel: { region: 'Middle East', stability: 2, battleground: true, adjacent_countries: [] },
  Canada: { region: 'Europe', stability: 4, battleground: false, adjacent_countries: [] },
  Norway: { region: 'Europe', stability: 4, battleground: false, adjacent_countries: [] },
  Sweden: { region: 'Europe', stability: 4, battleground: false, adjacent_countries: [] },
  Denmark: { region: 'Europe', stability: 3, battleground: false, adjacent_countries: [] },
  Benelux: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Italy: { region: 'Europe', stability: 2, battleground: true, adjacent_countries: [] },
  Greece: { region: 'Europe', stability: 2, battleground: true, adjacent_countries: [] },
  Poland: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  'E. Germany': { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Czechoslovakia: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Hungary: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Romania: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Bulgaria: { region: 'Europe', stability: 3, battleground: true, adjacent_countries: [] },
  Algeria: { region: 'Africa', stability: 2, battleground: false, adjacent_countries: [] },
  Tunisia: { region: 'Africa', stability: 2, battleground: false, adjacent_countries: [] },
  Angola: { region: 'Africa', stability: 1, battleground: false, adjacent_countries: [] },
  Botswana: { region: 'Africa', stability: 1, battleground: false, adjacent_countries: [] },
  'South Africa': { region: 'Africa', stability: 3, battleground: false, adjacent_countries: ['Botswana', 'Angola'] },
  Nigeria: { region: 'Africa', stability: 1, battleground: false, adjacent_countries: [] },
  India: { region: 'Asia', stability: 3, battleground: true, adjacent_countries: [] },
  Pakistan: { region: 'Asia', stability: 2, battleground: true, adjacent_countries: [] },
  Japan: { region: 'Asia', stability: 4, battleground: true, adjacent_countries: [] },
  Colombia: { region: 'South America', stability: 1, battleground: false, adjacent_countries: [] },
  Nicaragua: { region: 'Central America', stability: 1, battleground: false, adjacent_countries: [] },
  Guatemala: { region: 'Central America', stability: 1, battleground: false, adjacent_countries: [] },
  Mexico: { region: 'Central America', stability: 2, battleground: false, adjacent_countries: [] },
  Lebanon: { region: 'Middle East', stability: 1, battleground: false, adjacent_countries: [] },
  Egypt: { region: 'Middle East', stability: 2, battleground: true, adjacent_countries: [] },
  Iran: { region: 'Middle East', stability: 2, battleground: true, adjacent_countries: [] },
  Jordan: { region: 'Middle East', stability: 2, battleground: false, adjacent_countries: [] },
};

function renderBoard(cardId = 30, Component: any = TwilightStruggleBoard, chinaOwner = 'us', victoryPoints = -1, defcon = cardId === 100 ? 2 : 5) {
  const cardNames: Record<number, string> = { 7: 'Socialist Governments', 16: 'Warsaw Pact Formed', 28: 'Suez Crisis', 33: 'De-Stalinization', 53: 'South African Unrest', 70: 'OAS Founded', 74: 'The Voice of America', 75: 'Liberation Theology', 76: 'Ussuri River Skirmish', 77: 'Ask Not What Your Country Can Do For You', 85: 'Star Wars', 87: 'The Reformer', 88: 'Marine Barracks Bombing', 96: 'Tear Down This Wall', 99: 'Pershing II Deployed', 100: 'Wargames', 108: 'Our Man in Tehran' };
  const card = { id: cardId, name: cardNames[cardId] || 'Decolonization', operations: 2, alignment: 'ussr', card_face_asset: 'TNRnTS-30.svg' };
  const result = render(Component, {
    props: {
      screenState: {
        current_player: 'player_1',
          legal_moves: [{ type: 'play_card', move_id: `play-ussr-${cardId}`, card_id: cardId, modes: ['event', 'operations'] }],
        phase: { phase_name: 'action_round' },
        game_data: {
          current_phase: 'action_round', faction_by_player: { player_1: 'ussr' }, china_card: { owner: chinaOwner }, discard_pile: [{ id: 5, name: 'Five Year Plan', operations: 3, scoring: false, special: false }],
          hand: [card], countries: Object.fromEntries(Object.keys(countryInfo).map((name) => [name, { us: ['France', 'Israel'].includes(name) && cardId === 28 ? 2 : name === 'France' && cardId === 7 ? 2 : ['France', 'Norway', 'Sweden', 'Italy', 'U.K.', 'Israel', 'Lebanon', 'Egypt', 'Jordan'].includes(name) ? 1 : name === 'Iran' ? 2 : 0, ussr: name === 'E. Germany' ? 3 : ['India', 'Pakistan', 'Japan'].includes(name) ? 2 : 0 }])),
          map_positions: mapPositions, country_info: countryInfo, superpower_adjacency: [], tracks: { defcon, victory_points: victoryPoints, space_race: { us: 4, ussr: cardId === 85 ? 3 : 4 } },
        },
      },
    },
  });
  return result;
}

describe('Twilight Struggle board interaction', () => {
  it('zooms the map in and resets to its original size', async () => {
    const { container } = renderBoard();
    const map = container.querySelector('.world-map');
    expect(map?.getAttribute('style')).toContain('100%');
    await fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
    expect(map?.getAttribute('style')).toContain('125%');
    await fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(map?.getAttribute('style')).toContain('100%');
  });

  it('shows the hand as card faces below the board', () => {
    const { container } = renderBoard();
    const hand = container.querySelector('.hand-panel');
    expect(hand?.querySelector('.hand-card img')?.getAttribute('src')).toContain('TNRnTS-30.svg');
    expect(hand?.querySelector('.hand-list')).toBeTruthy();
  });

  it('builds a structured four-country event choice instead of JSON text', async () => {
    renderBoard();
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.queryByLabelText(/Event choices/i)).toBeNull();
    await fireEvent.click(screen.getByRole('button', { name: 'Algeria' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Tunisia' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Angola' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Nigeria' }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it.each([43, 67, 49])('keeps optional card %s event choices playable without a selection', async (cardId) => {
    renderBoard(cardId);
    await fireEvent.click(screen.getByRole('button', { name: /De-Stalinization/ }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('requires seven eligible countries for Marshall Plan', async () => {
    renderBoard(23);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.getByRole('group', { name: 'Event country choices' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Poland' })).toBeNull();
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (const country of ['Canada', 'Norway', 'Sweden', 'Denmark', 'Benelux', 'Italy', 'Greece']) {
      await fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${country}$`) }));
    }
    expect(play.disabled).toBe(false);
  });

  it.each([
    [24, 'India'],
    [36, 'Colombia'],
  ])('offers a guided legal target for card %s', async (cardId, target) => {
    renderBoard(cardId);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.queryByLabelText(/Advanced event choices/i)).toBeNull();
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.change(screen.getByLabelText('Choose a country'), { target: { value: target } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByLabelText('Choose a country') as HTMLSelectElement).value).toBe(target);
  });

  it.each([
    [45, 'Summit DEFCON choice', '-1'],
    [100, 'Wargames decision', 'end'],
  ])('shows a guided choice for card %s', async (cardId, label, value) => {
    renderBoard(cardId);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.queryByLabelText(/Advanced event choices/i)).toBeNull();
    const choice = screen.getByLabelText(label) as HTMLSelectElement;
    await fireEvent.change(choice, { target: { value } });
    expect(choice.value).toBe(value);
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it.each([
    [24, 'India', { indo_pakistani_war: 'India' }],
    [36, 'Colombia', { brush_war: 'Colombia' }],
    [45, '-1', { summit_defcon: -1 }],
    [100, 'end', { wargames: true }],
  ])('dispatches the expected structured payload for card %s', async (cardId, value, eventChoices) => {
    renderBoard(cardId, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    if (cardId === 24 || cardId === 36) {
      await fireEvent.change(screen.getByLabelText('Choose a country'), { target: { value } });
    } else {
      const label = cardId === 45 ? 'Summit DEFCON choice' : 'Wargames decision';
      await fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move).toEqual(expect.objectContaining({ card_id: cardId, mode: 'event', event_choices: eventChoices }));
  });

  it('dispatches Pershing II targets under card 99 and allows no targets', async () => {
    renderBoard(99, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Pershing II Deployed/ }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move).toEqual(expect.objectContaining({ card_id: 99, mode: 'event', event_choices: { pershing_ii_deployed: [] } }));
  });

  it('dispatches a selected Pershing II target', async () => {
    renderBoard(99, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Pershing II Deployed/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'France' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ pershing_ii_deployed: ['France'] });
  });

  it('does not render Pershing II controls for card 96', async () => {
    renderBoard(96);
    await fireEvent.click(screen.getByRole('button', { name: /Tear Down This Wall/ }));
    expect(screen.queryByRole('group', { name: 'Event country choices' })).toBeNull();
  });

  it.each([
    [{ Colombia: 2 }, ['Colombia', 2]],
    [{ Nicaragua: 1, Colombia: 1 }, ['Nicaragua', 1, 'Colombia', 1]],
  ])('dispatches a legal OAS Founded allocation %j', async (expected, allocation) => {
    renderBoard(70, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /OAS Founded/ }));
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (let index = 0; index < allocation.length; index += 2) {
      const country = allocation[index] as string;
      const amount = allocation[index + 1] as number;
      await fireEvent.change(screen.getByLabelText(`OAS influence in ${country}`), { target: { value: String(amount) } });
    }
    expect(play.disabled).toBe(false);
    await fireEvent.click(play);
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ oas_founded: expected });
  });

  it('allows Marine Barracks Bombing with no optional removals', async () => {
    renderBoard(88, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Marine Barracks Bombing/ }));
    expect(screen.queryByLabelText('Additional US influence removed from Lebanon')).toBeNull();
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ marine_barracks_bombing: {} });
  });

  it('dispatches a split Marine Barracks allocation and omits zero amounts', async () => {
    renderBoard(88, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Marine Barracks Bombing/ }));
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Egypt'), { target: { value: '1' } });
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Jordan'), { target: { value: '0' } });
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Iran'), { target: { value: '1' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ marine_barracks_bombing: { Egypt: 1, Iran: 1 } });
  });

  it('rejects Marine Barracks allocations above two total influence', async () => {
    renderBoard(88);
    await fireEvent.click(screen.getByRole('button', { name: /Marine Barracks Bombing/ }));
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Egypt'), { target: { value: '1' } });
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Iran'), { target: { value: '1' } });
    await fireEvent.change(screen.getByLabelText('Additional US influence removed from Jordan'), { target: { value: '1' } });
    expect(screen.getByText('Additional influence selected: 3 / 2')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    [{ Mexico: 2, Nicaragua: 1 }, [['Mexico', 2], ['Nicaragua', 1]]],
    [{ Guatemala: 1, Mexico: 1, Nicaragua: 1 }, [['Guatemala', 1], ['Mexico', 1], ['Nicaragua', 1]]],
  ])('dispatches a valid Liberation Theology allocation %j', async (expected, allocation) => {
    renderBoard(75, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Liberation Theology/ }));
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (const [country, amount] of allocation) {
      await fireEvent.change(screen.getByLabelText(`USSR influence placed in ${country}`), { target: { value: String(amount) } });
    }
    expect(play.disabled).toBe(false);
    await fireEvent.click(play);
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ liberation_theology: expected });
  });

  it('rejects Liberation Theology allocations that do not total three', async () => {
    renderBoard(75);
    await fireEvent.click(screen.getByRole('button', { name: /Liberation Theology/ }));
    await fireEvent.change(screen.getByLabelText('USSR influence placed in Mexico'), { target: { value: '2' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    [{ Botswana: 2 }, [['Botswana', 2]]],
    [{ Angola: 1, Botswana: 1 }, [['Angola', 1], ['Botswana', 1]]],
  ])('dispatches South African Unrest adjacent allocation %j', async (expected, allocation) => {
    renderBoard(53, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /South African Unrest/ }));
    await fireEvent.change(screen.getByLabelText('Placement choice'), { target: { value: 'adjacent' } });
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (const [country, amount] of allocation) {
      await fireEvent.change(screen.getByLabelText(`USSR influence placed in ${country}`), { target: { value: String(amount) } });
    }
    expect(play.disabled).toBe(false);
    await fireEvent.click(play);
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ south_african_unrest: { mode: 'adjacent', adjacent: expected } });
  });

  it('keeps South African Unrest adjacent mode disabled until exactly two are allocated', async () => {
    renderBoard(53);
    await fireEvent.click(screen.getByRole('button', { name: /South African Unrest/ }));
    await fireEvent.change(screen.getByLabelText('Placement choice'), { target: { value: 'adjacent' } });
    await fireEvent.change(screen.getByLabelText('USSR influence placed in Botswana'), { target: { value: '1' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    [{ France: 1, Italy: 1, Norway: 1 }, [['France', 1], ['Italy', 1], ['Norway', 1]]],
    [{ France: 2, Italy: 1 }, [['France', 2], ['Italy', 1]]],
  ])('dispatches Socialist Governments distribution %j', async (expected, allocation) => {
    renderBoard(7, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (const [country, amount] of allocation) {
      await fireEvent.change(screen.getByLabelText(`US influence removed from ${country}`), { target: { value: String(amount) } });
    }
    expect(play.disabled).toBe(false);
    await fireEvent.click(play);
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ socialist_governments: expected });
  });

  it('does not allow Socialist Governments to remove more US influence than held', async () => {
    renderBoard(7);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    const italy = screen.getByLabelText('US influence removed from Italy') as HTMLSelectElement;
    expect(Array.from(italy.options).map((option) => option.value)).toEqual(['0', '1']);
    await fireEvent.change(italy, { target: { value: '1' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each([
    [{ France: 2, Israel: 2 }, [['France', 2], ['Israel', 2]]],
    [{ France: 2, Israel: 1, 'U.K.': 1 }, [['France', 2], ['Israel', 1], ['U.K.', 1]]],
  ])('dispatches a legal Suez Crisis distribution %j', async (expected, allocation) => {
    renderBoard(28, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    const play = screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement;
    expect(play.disabled).toBe(true);
    for (const [country, amount] of allocation) {
      await fireEvent.change(screen.getByLabelText(`US influence removed from ${country}`), { target: { value: String(amount) } });
    }
    expect(play.disabled).toBe(false);
    await fireEvent.click(play);
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ suez_crisis: expected });
  });

  it('allows Voice of America to decline removals and supports a two-plus-one allocation', async () => {
    renderBoard(74, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.change(screen.getByLabelText('USSR influence removed from India'), { target: { value: '2' } });
    await fireEvent.change(screen.getByLabelText('USSR influence removed from Pakistan'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ the_voice_of_america: { India: 2, Pakistan: 1 } });
  });

  it('does not offer Wargames victory when six VP would tie the track', async () => {
    renderBoard(100, TwilightStruggleBoard, 'us', 6);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    const choice = screen.getByLabelText('Wargames decision') as HTMLSelectElement;
    expect(Array.from(choice.options).map((option) => option.value)).toEqual(['decline']);
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('dispatches Star Wars with the selected eligible discard card', async () => {
    renderBoard(85, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Star Wars/ }));
    await fireEvent.change(screen.getByLabelText('Choose a card'), { target: { value: '5' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ star_wars: 5 });
  });

  it('preserves a nested choice payload for a choice-requiring Star Wars discard', async () => {
    renderBoard(85, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Star Wars/ }));
    await fireEvent.change(screen.getByLabelText('Choose a card'), { target: { value: '5' } });
    await fireEvent.change(screen.getByLabelText('Selected card event choices (JSON)'), { target: { value: '{"five_year_plan": 12}' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ star_wars: 5, five_year_plan: 12 });
  });

  it('dispatches a valid De-Stalinization relocation with matching totals', async () => {
    renderBoard(33, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /De-Stalinization/ }));
    await fireEvent.change(screen.getByLabelText('USSR influence removed from E. Germany'), { target: { value: '3' } });
    await fireEvent.change(screen.getByLabelText('USSR influence placed in Poland'), { target: { value: '2' } });
    await fireEvent.change(screen.getByLabelText('USSR influence placed in Hungary'), { target: { value: '1' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ de_stalinization: { from: { 'E. Germany': 3 }, to: { Poland: 2, Hungary: 1 } } });
  });

  it('dispatches Junta with a Central or South American target', async () => {
    renderBoard(47, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Junta/ }));
    const choice = screen.getByLabelText('Choose a country') as HTMLSelectElement;
    expect(Array.from(choice.options).map((option) => option.value)).toContain('Colombia');
    expect(Array.from(choice.options).map((option) => option.value)).not.toContain('France');
    await fireEvent.change(choice, { target: { value: 'Colombia' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ junta: 'Colombia' });
  });

  it('attaches a valid Junta bonus realignment to the event payload', async () => {
    renderBoard(47, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Junta/ }));
    await fireEvent.change(screen.getByLabelText('Choose a country'), { target: { value: 'Colombia' } });
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    await fireEvent.change(screen.getByLabelText('Bonus target country'), { target: { value: 'Colombia' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ junta: 'Colombia', bonus_operations: { type: 'realignment', targets: [{ country: 'Colombia' }] } });
  });

  it('attaches an ordinary one-point CIA bonus influence action', async () => {
    renderBoard(26, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    await fireEvent.change(screen.getByLabelText('Bonus action'), { target: { value: 'influence' } });
    await fireEvent.change(screen.getByLabelText('Bonus target country'), { target: { value: 'France' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ bonus_operations: { type: 'influence', placements: [{ country: 'France', points: 1 }] } });
  });

  it('submits a multi-placement CIA bonus within its one-point budget', async () => {
    renderBoard(26, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    await fireEvent.change(screen.getByLabelText('Bonus target country'), { target: { value: 'France' } });
    await fireEvent.change(screen.getByLabelText('Bonus influence points'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices.bonus_operations.placements).toEqual([{ country: 'France', points: 1 }]);
  });

  it('submits an Ortega bonus coup using the USSR as the beneficiary', async () => {
    renderBoard(91, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    await fireEvent.change(screen.getByLabelText('Bonus target country'), { target: { value: 'Colombia' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices.bonus_operations).toEqual({ type: 'coup', country: 'Colombia' });
  });

  it('dispatches Tehran discard subset response IDs from the private revealed-card move', async () => {
    render(TwilightBoardEventCapture, { props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_response', player_id: 'player_1', decision: 'discard_revealed_cards', revealed_cards: [{ id: 5, name: 'Five Year Plan' }, { id: 7, name: 'Socialist Governments' }] }], game_data: { current_phase: 'event_response', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } } });
    await fireEvent.click(screen.getByLabelText(/Five Year Plan/));
    await fireEvent.click(screen.getByRole('button', { name: 'Confirm discards' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move).toEqual({ type: 'event_response', player_id: 'player_1', decision: 'discard_revealed_cards', card_ids: [5] });
  });

  it('offers only legal event-bonus action kinds and filters the regional target list', async () => {
    renderBoard(91, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.queryByRole('option', { name: 'Place influence' })).toBeNull();
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    expect(Array.from((screen.getByLabelText('Bonus action') as HTMLSelectElement).options).map((option) => option.value)).toEqual(['coup']);
    const targets = Array.from((screen.getByLabelText('Bonus target country') as HTMLSelectElement).options).map((option) => option.value);
    expect(targets).toContain('Colombia');
    expect(targets).not.toContain('France');
  });

  it('restricts the Ortega bonus target list to Nicaragua neighbors', async () => {
    const { container } = renderBoard(91);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    const options = Array.from((screen.getByLabelText('Bonus target country') as HTMLSelectElement).options).map((option) => option.value);
    expect(options).toContain('Colombia');
    expect(options).not.toContain('France');
    expect(container.querySelector('[aria-label="Advanced event choices (JSON)"]')).toBeNull();
  });

  it('offers European coup targets for Tear Down This Wall at DEFCON 4', async () => {
    renderBoard(96, TwilightBoardEventCapture, 'us', -1, 4);
    await fireEvent.click(screen.getByRole('button', { name: /Tear Down This Wall/ }));
    await fireEvent.click(screen.getByLabelText('Add optional bonus Operations'));
    await fireEvent.change(screen.getByLabelText('Bonus action'), { target: { value: 'coup' } });
    const targets = Array.from((screen.getByLabelText('Bonus target country') as HTMLSelectElement).options).map((option) => option.value);
    expect(targets).toContain('France');
    expect(targets).not.toContain('Colombia');
  });

  it('keeps De-Stalinization disabled when source and destination totals differ', async () => {
    renderBoard(33);
    await fireEvent.click(screen.getByRole('button', { name: /De-Stalinization/ }));
    await fireEvent.change(screen.getByLabelText('USSR influence removed from E. Germany'), { target: { value: '2' } });
    await fireEvent.change(screen.getByLabelText('USSR influence placed in Poland'), { target: { value: '1' } });
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('dispatches supplied staged event-response moves unchanged', async () => {
    const { rerender } = render(TwilightBoardEventCapture, {
      props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_response', player_id: 'player_1', decision: 'choose_country', country: 'France' }], game_data: { current_phase: 'event_response', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } }, },
    });
    await fireEvent.click(screen.getByRole('button', { name: /choose country.*France/i }));
    expect(JSON.parse(screen.getByTestId('captured-move').textContent || '{}')).toEqual({ type: 'event_response', player_id: 'player_1', decision: 'choose_country', country: 'France' });
    await rerender({ screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_response', player_id: 'player_1', decision: 'discard', card_id: 12 }], game_data: { current_phase: 'event_response', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } });
  });

  it('dispatches staged bonus decline exactly as supplied', async () => {
    render(TwilightBoardEventCapture, { props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_bonus', player_id: 'player_1', decline: true }], game_data: { current_phase: 'event_bonus', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } } });
    await fireEvent.click(screen.getByRole('button', { name: /event bonus/i }));
    expect(JSON.parse(screen.getByTestId('captured-move').textContent || '{}')).toEqual({ type: 'event_bonus', player_id: 'player_1', decline: true });
  });

  it('attaches the guided operations action to staged bonus and card operations moves', async () => {
    const { rerender } = render(TwilightBoardEventCapture, { props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_bonus', player_id: 'player_1', decline: false }], game_data: { current_phase: 'event_bonus', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } } });
    await fireEvent.change(screen.getByLabelText('Operations'), { target: { value: 'space_race' } });
    await fireEvent.click(screen.getByRole('button', { name: /event bonus/i }));
    expect(JSON.parse(screen.getByTestId('captured-move').textContent || '{}')).toEqual({ type: 'event_bonus', player_id: 'player_1', decline: false, operations_action: { type: 'space_race' } });
    await rerender({ screenState: { current_player: 'player_1', legal_moves: [{ type: 'card_operations', player_id: 'player_1' }], game_data: { current_phase: 'card_operations', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } });
    await fireEvent.click(screen.getByRole('button', { name: /card operations/i }));
    expect(JSON.parse(screen.getByTestId('captured-move').textContent || '{}')).toEqual({ type: 'card_operations', player_id: 'player_1', operations_action: { type: 'space_race' } });
  });

  it('restricts staged card operations to influence/realignment and bonus actions away from Space Race', async () => {
    const { rerender } = render(TwilightBoardEventCapture, { props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'card_operations', player_id: 'player_1' }], game_data: { current_phase: 'card_operations', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } } });
    const stagedType = screen.getByLabelText('Operations') as HTMLSelectElement;
    expect(Array.from(stagedType.options).map((option) => option.value)).toEqual(['influence', 'realignment']);
    await rerender({ screenState: { current_player: 'player_1', legal_moves: [{ type: 'event_bonus', player_id: 'player_1', decline: false }], game_data: { current_phase: 'event_bonus', faction_by_player: { player_1: 'us' }, countries: {}, hand: [] } } });
    expect(Array.from((screen.getByLabelText('Operations') as HTMLSelectElement).options).map((option) => option.value)).toEqual(['influence', 'coup', 'realignment']);
  });

  it('submits multi-target staged card influence with unchanged actor and stage', async () => {
    render(TwilightBoardEventCapture, { props: { screenState: { current_player: 'player_1', legal_moves: [{ type: 'card_operations', player_id: 'player_1' }], game_data: { current_phase: 'card_operations', faction_by_player: { player_1: 'us' }, countries: { France: { us: 0, ussr: 0 }, Italy: { us: 0, ussr: 0 } }, country_info: countryInfo, superpower_adjacency: [['France', 'United States'], ['Italy', 'United States']], hand: [] } } } });
    await fireEvent.change(screen.getByLabelText('Operations'), { target: { value: 'influence' } });
    await fireEvent.change(screen.getByLabelText('Influence points'), { target: { value: '2' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Add another placement' }));
    await fireEvent.change(screen.getByLabelText('Placement 1 points'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: /card operations/i }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move).toEqual({ type: 'card_operations', player_id: 'player_1', operations_action: { type: 'influence', placements: [{ country: 'France', points: 1 }] } });
  });

  it('lets Ask Not discard selected held cards but never the card being played', async () => {
    renderBoard(77, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    expect(screen.queryByRole('button', { name: /Ask Not What/ })).toBeNull();
    await fireEvent.click(screen.getByRole('button', { name: /Play card/ }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ ask_not_what: [] });
  });

  it('dispatches a rule-legal Warsaw Pact influence distribution', async () => {
    renderBoard(16, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.change(screen.getByLabelText('Warsaw Pact choice'), { target: { value: 'add_ussr' } });
    for (const [country, amount] of [['E. Germany', 2], ['Poland', 2], ['Czechoslovakia', 1]]) {
      await fireEvent.change(screen.getByLabelText(`USSR influence placed in ${country}`), { target: { value: String(amount) } });
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({
      warsaw_pact_formed: {
        mode: 'add_ussr',
        distribution: { 'E. Germany': 2, Poland: 2, Czechoslovakia: 1 },
      },
    });
  });

  it('dispatches a four-country Warsaw Pact placement distribution', async () => {
    renderBoard(16, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /Decolonization/ }));
    await fireEvent.change(screen.getByLabelText('Warsaw Pact choice'), { target: { value: 'add_ussr' } });
    const allocation: Array<[string, number]> = [['E. Germany', 2], ['Poland', 1], ['Czechoslovakia', 1], ['Hungary', 1]];
    for (const [country, amount] of allocation) {
      await fireEvent.change(screen.getByLabelText(`USSR influence placed in ${country}`), { target: { value: String(amount) } });
    }
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({
      warsaw_pact_formed: {
        mode: 'add_ussr',
        distribution: { 'E. Germany': 2, Poland: 1, Czechoslovakia: 1, Hungary: 1 },
      },
    });
  });

  it('dispatches an exact Ussuri placement across Asian countries', async () => {
    renderBoard(76, TwilightBoardEventCapture, 'us');
    await fireEvent.click(screen.getByRole('button', { name: /Ussuri River Skirmish/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Add India' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Add Pakistan' }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
    await fireEvent.click(screen.getByRole('button', { name: '2 influence in India' }));
    await fireEvent.click(screen.getByRole('button', { name: '2 influence in Pakistan' }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(false);
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ ussuri_river_skirmish: { India: 2, Pakistan: 2 } });
  });

  it('sends no placement choice when Ussuri transfers the China Card from USSR', async () => {
    renderBoard(76, TwilightBoardEventCapture, 'ussr');
    await fireEvent.click(screen.getByRole('button', { name: /Ussuri River Skirmish/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toBeUndefined();
  });

  it('does not allow Ussuri to place all four influence in one country', async () => {
    renderBoard(76, TwilightBoardEventCapture, 'us');
    await fireEvent.click(screen.getByRole('button', { name: /Ussuri River Skirmish/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Add India' }));
    await fireEvent.click(screen.getByRole('button', { name: '2 influence in India' }));
    expect((screen.getByRole('button', { name: 'Play card' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('dispatches mixed Reformer placement totaling six when USSR is ahead', async () => {
    renderBoard(87, TwilightBoardEventCapture);
    await fireEvent.click(screen.getByRole('button', { name: /The Reformer/ }));
    for (const [country, amount] of [['France', 2], ['Italy', 2], ['Norway', 2]]) {
      await fireEvent.change(screen.getByLabelText(`USSR influence placed in ${country}`), { target: { value: String(amount) } });
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Play card' }));
    const move = JSON.parse(screen.getByTestId('captured-move').textContent || '{}');
    expect(move.event_choices).toEqual({ reformer: { France: 2, Italy: 2, Norway: 2 } });
  });
});
