import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const DEFAULT_SETTINGS = {
  hover_zoom_percent: 150,
};

function createSettingsStore() {
  const { subscribe, set, update } = writable({ ...DEFAULT_SETTINGS });

  return {
    subscribe,
    set,
    update,
    async load() {
      if (!browser) return;
      try {
        const res = await fetch('/api/v1/settings');
        if (res.ok) {
          const data = await res.json();
          set({ ...DEFAULT_SETTINGS, ...data });
        }
      } catch (e) {
        console.warn('Failed to load settings, using defaults');
      }
    },
    async save(settings) {
      if (!browser) return;
      set(settings);
      try {
        await fetch('/api/v1/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings),
        });
      } catch (e) {
        console.error('Failed to save settings:', e);
      }
    },
    reset() {
      set({ ...DEFAULT_SETTINGS });
    }
  };
}

export const settings = createSettingsStore();
