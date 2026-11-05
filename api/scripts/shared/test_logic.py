# Test the fix logic
state = {
    'phase': 'setup',  # top level from initial_game_data
    'game': 'fields_of_fire',
    'current_player': 'player_1',
    'turn': 1,
}

# This is what validate_move does now:
gd = state.get('game_data', {})  # no 'game_data' key, so {}
phase = gd.get('phase')  # None since gd is {}

# The fix:
if phase is None:
    phase = state.get('phase')  # get from top level = 'setup'

mtype = 'start_mission'
if mtype == 'start_mission' and phase == 'setup':
    print('RESULT: validate_move returns TRUE - user can start a game!')
else:
    print('RESULT: validate_move returns FALSE')