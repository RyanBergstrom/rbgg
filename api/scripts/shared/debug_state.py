from app.games.fields_of_fire.validator import FieldsOfireValidator
import sys
try:
    validator = FieldsOfireValidator()
except NameError:
    from app.games.fields_of_fire.validator import FieldsOfireValidator
    validator = FieldsOfireValidator()
state = validator.initial_game_data()
print('Keys:', list(state.keys()))
print('Phase:', state.get('phase'))
print('game_data in state:', 'game_data' in state)
gd = state.get('game_data', {})
print('game_data keys:', list(gd.keys()) if isinstance(gd, dict) else type(gd))