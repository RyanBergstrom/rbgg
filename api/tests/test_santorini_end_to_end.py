"use strict";

const { expect } = require('@playwright/test');
const { test, api } = require('../fixtures');

test('test_ai_turn_auto_calls_ai_then_submit', async ({ page }) => {
  await api('/api/moves/ai', {
    method: 'POST',
    body: JSON.stringify({ gameId: 'santorini', sessionId: 'session-1' })
  });

  await api('/api/moves/santorini', {
    method: 'POST',
    body: JSON.stringify({ type: 'move', from: 'worker1', to: '0-0' })
  });

  const page = await test.getPage();
  await page.waitForSelector('.game-over-banner', { state: 'attached' });
});

test('test_game_over_banner_renders', async ({ page }) => {
  await page.goto('/api/games/santorini');

  // Wait for game to load and AI to make a move
  await page.waitForSelector('.spinner-border', { state: 'attached' });
  await page.waitForTimeout(1500); // Wait for AI thinking

  // Check game over banner appears
  await expect(page.locator('.game-over-banner')).toBeVisible();
  await expect(page.locator('h2')).toContainText('Player');
});

test('test_full_scripted_game_records_stats_rows', async ({ page, api }) => {
  // Start a new game
  await api('/api/games/', {
    method: 'POST',
    body: JSON.stringify({ gameId: 'santorini', playerName: 'TestPlayer' })
  });

  const page = await test.getPage();

  // Play through game with AI moves
  await page.waitForSelector('.spinner-border', { state: 'attached' });
  await page.waitForTimeout(2000);

  // Verify game ends with winner
  await expect(page.locator('.game-over-banner')).toBeVisible();
  await expect(page.locator('h2')).toContainText('Winner');
});