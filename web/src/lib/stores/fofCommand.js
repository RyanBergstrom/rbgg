import { writable } from 'svelte/store';

// Command controls for Fields of Fire. The board publishes its command state here,
// and the footer (GameProgressPanel) renders the buttons in its right-hand area.
// null means no command controls are active (other games, or Fields of Fire setup).
export const fofCommand = writable(null);
