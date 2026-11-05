import { test, expect } from '@playwright/test';

test('Bus action selection buttons should not be disabled', async ({ page }) => {
  // Enable console logging
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  
  // Navigate to setup page
  await page.goto('http://127.0.0.1:5173/games/bus/setup');
  
  // Wait for the page to load
  await page.waitForSelector('button:has-text("Start Game")', { timeout: 10000 });
  console.log('Found Start Game button');
  
  // Click "Start Game" (defaults: name "Ryan", 3 players)
  // This triggers a client-side navigation via window.location.href
  await page.click('button:has-text("Start Game")');
  console.log('Clicked Start Game button');
  
  // Wait for navigation to the play page - use waitForURL with a longer timeout
  // The navigation is done via window.location.href so we need to wait for it
  await page.waitForURL('**/games/bus/play?sessionId=*', { timeout: 30000 });
  console.log('On play page:', page.url());
  
  // Wait for the BusBoard component to load
  await page.waitForSelector('.bus-board', { timeout: 10000 });
  console.log('BusBoard loaded');
  
  // SETUP_BUILDINGS phase - first building
  // Wait for building buttons to be clickable
  await page.waitForSelector('button.site.legal:not(:disabled)', { timeout: 10000 });
  
  // Click first available building
  const firstBuilding = page.locator('button.site.legal:not(:disabled)').first();
  await firstBuilding.click();
  
  // Wait for building type picker and select house
  await page.waitForSelector('button:has-text("house")', { timeout: 5000 });
  await page.click('button:has-text("house")');
  
  // Wait for bots to finish their building placements (~3-4s)
  await page.waitForTimeout(5000);
  
  // Second building placement for human
  await page.waitForSelector('button.site.legal:not(:disabled)', { timeout: 10000 });
  const secondBuilding = page.locator('button.site.legal:not(:disabled)').first();
  await secondBuilding.click();
  
  // Select house again
  await page.waitForSelector('button:has-text("house")', { timeout: 5000 });
  await page.click('button:has-text("house")');
  
  // Wait for bots to finish
  await page.waitForTimeout(5000);
  
  // SETUP_FIRST_ROUTE_SEGMENTS phase
  // Click a legal route segment on the map (using force since it may be behind other elements)
  await page.waitForSelector('.legal-route', { timeout: 10000 });
  await page.locator('.legal-route').first().click({ force: true });
  
  // Wait for bots
  await page.waitForTimeout(5000);
  
  // SETUP_SECOND_ROUTE_SEGMENTS phase - click first route segment button
  await page.waitForSelector('button:has-text("Build route segment")', { timeout: 10000 });
  await page.click('button:has-text("Build route segment")');
  
  // Wait for transition to ACTION_SELECTION
  await page.waitForTimeout(3000);
  
  // Now we should be in ACTION_SELECTION phase
  // Check that action-slot buttons are not all disabled
  const actionButtons = page.locator('.board-action-slot');
  const count = await actionButtons.count();
  console.log(`Total action buttons: ${count}`);
  
  // Get all button states
  const buttonStates = await actionButtons.evaluateAll(buttons => 
    buttons.map(btn => ({
      label: btn.getAttribute('aria-label'),
      disabled: btn.disabled,
      classes: btn.className,
      moveDefined: btn.getAttribute('data-debug-move-defined'),
      selectableJson: btn.getAttribute('data-debug-selectable-json'),
    }))
  );
  
  console.log('Button states:', JSON.stringify(buttonStates, null, 2));
  
  // Find buttons that should be legal (not disabled)
  const legalButtons = buttonStates.filter(b => !b.disabled && b.classes.includes('legal'));
  console.log('Legal buttons:', legalButtons);
  
  // Check if any button has moveDefined=true
  const moveDefinedButtons = buttonStates.filter(b => b.moveDefined === 'true');
  console.log('Buttons with moveDefined=true:', moveDefinedButtons);
  
  // The bug: all buttons have moveDefined=false despite selectableActions having entries
  if (moveDefinedButtons.length === 0 && legalButtons.length === 0) {
    console.log('BUG REPRODUCED: All action buttons are disabled despite selectableActions having entries');
    
    // Let's inspect the selectableActions from the page
    const debugInfo = await page.evaluate(() => {
      // Get the selectableActions from the Svelte component
      const board = document.querySelector('.bus-board');
      if (board && board.__svelte_meta) {
        // We can't easily access Svelte internals, but we can check the debug attributes
        return 'Svelte component found';
      }
      return 'No Svelte component found';
    });
    console.log('Debug info:', debugInfo);
  }
  
  // This test should fail if the bug exists (no legal buttons)
  expect(legalButtons.length).toBeGreaterThan(0);
});