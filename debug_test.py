from api.app.core.config_schema import PhaseConfig, GameConfig, PanelConfig

panels = {
    'game_progress': PanelConfig(panel_id='game_progress', name='Game Progress'),
    'main_board': PanelConfig(panel_id='main_board', name='Main Board'),
}
try:
    phases = {'': PhaseConfig(name='')}
    config = GameConfig(panels=panels, components={}, phases=phases)
except ValueError as e:
    print('Caught ValueError:', e)
    s = str(e)
    print('str(e):', s)
    print('"phase name must be non-empty" in str(e):', 'phase name must be non-empty' in s)
    print('"empty" in str(e).lower():', 'empty' in s.lower())