# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests\unit\bus-bug-repro.test.ts >> Bus action selection buttons should not be disabled
- Location: tests\unit\bus-bug-repro.test.ts:3:1

# Error details

```
TimeoutError: page.waitForURL: Timeout 30000ms exceeded.
=========================== logs ===========================
waiting for navigation to "**/games/bus/play?sessionId=*" until "load"
============================================================
```

# Page snapshot

```yaml
- generic [ref=e4]:
  - generic [ref=e5]:
    - img "Bus cover" [ref=e6]
    - heading "Bus" [level=1] [ref=e8]
  - generic [ref=e9]:
    - button "← Exit" [ref=e11] [cursor=pointer]:
      - generic [ref=e12]: ←
      - text: Exit
    - generic [ref=e14]:
      - heading "New Game" [level=2] [ref=e15]
      - generic [ref=e16]:
        - generic [ref=e17]: Player Name
        - textbox "Player Name" [ref=e18]:
          - /placeholder: Enter your name
          - text: Ryan
      - generic [ref=e19]:
        - generic [ref=e20]: Number of Players
        - spinbutton "Number of Players" [ref=e21]: "3"
        - text: Choose from 3 to 5 players.
      - button "Start Game" [active] [ref=e22] [cursor=pointer]
    - generic [ref=e23]:
      - heading "Bus History" [level=2] [ref=e24]
      - generic "All-time completed game statistics" [ref=e25]:
        - generic [ref=e26]:
          - generic [ref=e27]: Completed
          - strong [ref=e28]: "5"
        - generic [ref=e29]:
          - generic [ref=e30]: Wins
          - strong [ref=e31]: "1"
        - generic [ref=e32]:
          - generic [ref=e33]: Losses
          - strong [ref=e34]: "4"
        - generic [ref=e35]:
          - generic [ref=e36]: Win rate
          - strong [ref=e37]: 20%
      - heading "Record against each bot" [level=3] [ref=e38]
      - table [ref=e40]:
        - rowgroup [ref=e41]:
          - row [ref=e42]:
            - columnheader "Opponent" [ref=e43]
            - columnheader "Games" [ref=e44]
            - columnheader "W–L–D" [ref=e45]
            - columnheader "Win rate" [ref=e46]
        - rowgroup [ref=e47]:
          - row [ref=e48]:
            - cell "Stacy" [ref=e49]
            - cell "5" [ref=e50]
            - cell "1–4–0" [ref=e51]
            - cell "20%" [ref=e52]
          - row [ref=e53]:
            - cell "Trey" [ref=e54]
            - cell "5" [ref=e55]
            - cell "1–4–0" [ref=e56]
            - cell "20%" [ref=e57]
      - heading "Completed games" [level=3] [ref=e58]
      - table [ref=e60]:
        - rowgroup [ref=e61]:
          - row [ref=e62]:
            - columnheader "Finished" [ref=e63]
            - columnheader "Result" [ref=e64]
            - columnheader "Opponents" [ref=e65]
            - columnheader "Your score" [ref=e66]
        - rowgroup [ref=e67]:
          - row [ref=e68]:
            - cell "10/17/2026" [ref=e69]
            - cell "Loss" [ref=e70]
            - cell "Stacy, Trey" [ref=e72]
            - cell "—" [ref=e73]
          - row [ref=e74]:
            - cell "10/17/2026" [ref=e75]
            - cell "Loss" [ref=e76]
            - cell "Stacy, Trey" [ref=e78]
            - cell "—" [ref=e79]
          - row [ref=e80]:
            - cell "10/17/2026" [ref=e81]
            - cell "Loss" [ref=e82]
            - cell "Stacy, Trey" [ref=e84]
            - cell "—" [ref=e85]
          - row [ref=e86]:
            - cell "10/17/2026" [ref=e87]
            - cell "Win" [ref=e88]
            - cell "Stacy, Trey" [ref=e90]
            - cell "—" [ref=e91]
          - row [ref=e92]:
            - cell "10/17/2026" [ref=e93]
            - cell "Loss" [ref=e94]
            - cell "Stacy, Trey" [ref=e96]
            - cell "—" [ref=e97]
```

# Test source

```ts
  1   | import { test, expect } from '@playwright/test';
  2   | 
  3   | test('Bus action selection buttons should not be disabled', async ({ page }) => {
  4   |   // Enable console logging
  5   |   page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  6   |   page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  7   |   
  8   |   // Navigate to setup page
  9   |   await page.goto('http://127.0.0.1:5173/games/bus/setup');
  10  |   
  11  |   // Wait for the page to load
  12  |   await page.waitForSelector('button:has-text("Start Game")', { timeout: 10000 });
  13  |   console.log('Found Start Game button');
  14  |   
  15  |   // Click "Start Game" (defaults: name "Ryan", 3 players)
  16  |   await page.click('button:has-text("Start Game")');
  17  |   console.log('Clicked Start Game button');
  18  |   
  19  |   // Wait for navigation - use waitForLoadState instead of waitForURL
  20  |   await page.waitForLoadState('networkidle', { timeout: 30000 });
  21  |   console.log('Navigation complete, current URL:', page.url());
  22  |   
  23  |   // Wait for the play page to load
> 24  |   await page.waitForURL('**/games/bus/play?sessionId=*', { timeout: 30000 });
      |              ^ TimeoutError: page.waitForURL: Timeout 30000ms exceeded.
  25  |   console.log('On play page:', page.url());
  26  |   
  27  |   // SETUP_BUILDINGS phase - first building
  28  |   // Wait for building buttons to be clickable
  29  |   await page.waitForSelector('button.site.legal:not(:disabled)', { timeout: 10000 });
  30  |   
  31  |   // Click first available building
  32  |   const firstBuilding = page.locator('button.site.legal:not(:disabled)').first();
  33  |   await firstBuilding.click();
  34  |   
  35  |   // Wait for building type picker and select house
  36  |   await page.waitForSelector('button:has-text("house")', { timeout: 5000 });
  37  |   await page.click('button:has-text("house")');
  38  |   
  39  |   // Wait for bots to finish their building placements (~3-4s)
  40  |   await page.waitForTimeout(5000);
  41  |   
  42  |   // Second building placement for human
  43  |   await page.waitForSelector('button.site.legal:not(:disabled)', { timeout: 10000 });
  44  |   const secondBuilding = page.locator('button.site.legal:not(:disabled)').first();
  45  |   await secondBuilding.click();
  46  |   
  47  |   // Select house again
  48  |   await page.waitForSelector('button:has-text("house")', { timeout: 5000 });
  49  |   await page.click('button:has-text("house")');
  50  |   
  51  |   // Wait for bots to finish
  52  |   await page.waitForTimeout(5000);
  53  |   
  54  |   // SETUP_FIRST_ROUTE_SEGMENTS phase
  55  |   // Click a legal route segment on the map (using force since it may be behind other elements)
  56  |   await page.waitForSelector('.legal-route', { timeout: 10000 });
  57  |   await page.locator('.legal-route').first().click({ force: true });
  58  |   
  59  |   // Wait for bots
  60  |   await page.waitForTimeout(5000);
  61  |   
  62  |   // SETUP_SECOND_ROUTE_SEGMENTS phase - click first route segment button
  63  |   await page.waitForSelector('button:has-text("Build route segment")', { timeout: 10000 });
  64  |   await page.click('button:has-text("Build route segment")');
  65  |   
  66  |   // Wait for transition to ACTION_SELECTION
  67  |   await page.waitForTimeout(3000);
  68  |   
  69  |   // Now we should be in ACTION_SELECTION phase
  70  |   // Check that action-slot buttons are not all disabled
  71  |   const actionButtons = page.locator('.board-action-slot');
  72  |   const count = await actionButtons.count();
  73  |   console.log(`Total action buttons: ${count}`);
  74  |   
  75  |   // Get all button states
  76  |   const buttonStates = await actionButtons.evaluateAll(buttons => 
  77  |     buttons.map(btn => ({
  78  |       label: btn.getAttribute('aria-label'),
  79  |       disabled: btn.disabled,
  80  |       classes: btn.className,
  81  |       moveDefined: btn.getAttribute('data-debug-move-defined'),
  82  |       selectableJson: btn.getAttribute('data-debug-selectable-json'),
  83  |     }))
  84  |   );
  85  |   
  86  |   console.log('Button states:', JSON.stringify(buttonStates, null, 2));
  87  |   
  88  |   // Find buttons that should be legal (not disabled)
  89  |   const legalButtons = buttonStates.filter(b => !b.disabled && b.classes.includes('legal'));
  90  |   console.log('Legal buttons:', legalButtons);
  91  |   
  92  |   // Check if any button has moveDefined=true
  93  |   const moveDefinedButtons = buttonStates.filter(b => b.moveDefined === 'true');
  94  |   console.log('Buttons with moveDefined=true:', moveDefinedButtons);
  95  |   
  96  |   // The bug: all buttons have moveDefined=false despite selectableActions having entries
  97  |   if (moveDefinedButtons.length === 0 && legalButtons.length === 0) {
  98  |     console.log('BUG REPRODUCED: All action buttons are disabled despite selectableActions having entries');
  99  |     
  100 |     // Let's inspect the selectableActions from the page
  101 |     const debugInfo = await page.evaluate(() => {
  102 |       // Get the selectableActions from the Svelte component
  103 |       const board = document.querySelector('.bus-board');
  104 |       if (board && board.__svelte_meta) {
  105 |         // We can't easily access Svelte internals, but we can check the debug attributes
  106 |         return 'Svelte component found';
  107 |       }
  108 |       return 'No Svelte component found';
  109 |     });
  110 |     console.log('Debug info:', debugInfo);
  111 |   }
  112 |   
  113 |   // This test should fail if the bug exists (no legal buttons)
  114 |   expect(legalButtons.length).toBeGreaterThan(0);
  115 | });
```