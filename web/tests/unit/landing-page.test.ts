import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import LandingPage from '../../src/routes/+page.svelte';

describe('LandingPage', () => {
  it('test_renders_initial_loading_state', () => {
    render(LandingPage);
    const main = screen.getByRole('main');
    expect(main).toBeTruthy();
  });

  it('test_renders_empty_state_when_no_games', () => {
    const { container } = render(LandingPage);
    const emptyState = container.querySelector('[data-testid="empty-state"]');
    expect(emptyState).toBeTruthy();
    expect(emptyState.querySelector('h2').textContent).toBe('No games found');
  });
});
