# Letters from Whitechapel: Digital Prototype Implementation Strategy & Wireframe Blueprint

## 1. Executive Summary & Product Vision
This document outlines the product requirements, user experience design, and business-friendly implementation roadmap for a digital adaptation of the board game *Letters from Whitechapel*. Designed primarily for personal testing and iterative rule verification, this web-based application prioritizes an immersive, clutter-free tactical interface. By stripping away extraneous UI layers and emphasizing customizability—such as a resizable split-pane layout and a unified bottom action bar—the platform maximizes visibility for the dense Whitechapel node grid while streamlining asymmetrical gameplay between Jack the Ripper and the Detectives.

---

## 2. Business & Product Goals
When transitioning a complex physical hidden-movement deduction game to a digital format, the implementation must focus on core value drivers:
* **Rule Enforcement & Automation:** Reduce human error in tracking turns, calculating distances, and validating movement adjacency across the 195 nodes, ensuring test sessions run smoothly without arguments over board state.
* **Asymmetrical Clarity:** Provide distinct visual and functional contexts for opposing players (secret tracking for Jack versus historical deduction logs for the Detectives) while maintaining an intuitive transition flow.
* **Ergonomic Workspace:** Maximize screen real estate for the map canvas to accommodate complex route planning, ensuring high usability across desktop monitors and tablet displays.
* **Iterative Agility:** Build a lightweight, modular product framework that allows rapid testing of house rules, variant mechanics, or balance tweaks during ongoing playtests.

---

## 3. User Interface & Layout Wireframe Architecture

The application layout utilizes an immersive, full-screen viewport with zero wasted vertical space. The top navigation bar has been removed, anchoring all meta-controls, phase tracking, and primary decision buttons into a unified bottom action bar.

```text
+-----------------------------------------------------------------------------------+
|                                                                                   |
|                                                                                   |
|                                       ||  [Tabs: Log / Suspects / Notes]          |
|                                       || +--------------------------------------+ |
|                                       || | 🕵️ DETECTIVE INVESTIGATION BOARD     | |
|          MAP / BOARD CANVAS           || | - Search History                     | |
|     (Whitechapel Grid - Scalable)     || | - Arrest Attempts                    | |
|                                       || | - Clue Markers / Alibis              | |
|   - Numbered Nodes (1-195)            || +--------------------------------------+ |
|   - Red/White Carriage Paths          ||                                          |
|   - Dark/Light Alleyways              || [Action Log Feed / Game History]         |
|                                       || - "Inspector 1 searched node 42"         |
|                                       || - "Jack moved secretly"                  |
|                                       ||                                          |
+---------------------------------------++------------------------------------------+
| [⚙️ Settings]  [Round/Phase Tracker]  ||  [Confirm] [Undo] [Pass / End Turn]      |
+-----------------------------------------------------------------------------------+
             ^
     (Draggable Splitter Handle `||`)
```

### Key Interface Zones & UX Specifications

1. **Map / Board Canvas (Primary Left Zone):**
   * **Purpose:** The core interactive visual workspace representing the Whitechapel district map grid.
   * **Features:** Displays numbered nodes ($1$ through $195$), street paths, dark/light alleyways, and special carriage/boat routes. 
   * **Reactivity:** Dynamically highlights valid movement options upon node selection and supports smooth zooming/panning to accommodate detailed tactical analysis.

2. **Draggable Split-Pane Handle (`||`):**
   * **Purpose:** Empowers users to customize their visual workspace dynamically.
   * **Features:** Allows players to drag the divider horizontally, expanding the map canvas to be wider when deep route-planning is required, or widening the side panel for detailed log inspection.

3. **Deduction & Status Sidebar (Right Zone):**
   * **Tabs Structure:** Houses modular sub-panels including the Investigation Log, Suspect Alibi tracker, personal scratchpad notes, and a chronological Action Log Feed capturing public history (e.g., searches, arrests, and phase transitions) for post-game analysis.

4. **Unified Bottom Action Bar:**
   * **Left Section:** Features a `[⚙️ Settings]` icon (for audio toggles, rules references, and session resets) right alongside the `[Round / Phase Tracker]` (displaying Night and Phase progress clearly).
   * **Right Section:** Houses context-sensitive operational buttons (`[Confirm]`, `[Undo]`, `[Pass / End Turn]`) grouped logically to prevent accidental moves and streamline turn flow.

---

## 4. Implementation Phasing & Rollout Strategy

To bring this digital test environment to life efficiently, the development lifecycle is divided into three business-focused milestones:

* **Phase 1: Core Mechanics & Board Graph Validation (The Foundation)**
  * *Objective:* Establish the foundational data model for the 195 nodes and movement adjacency rules.
  * *Business Value:* Ensures that physical board rules (street vs. alley vs. carriage constraints) are strictly coded and enforced digitally, eliminating illegal move errors during testing.

* **Phase 2: Layout, Wireframe, & Responsive UI Integration (The Workspace)**
  * *Objective:* Build the split-pane resizable interface, clean bottom action bar, and map canvas rendering.
  * *Business Value:* Delivers the ergonomic workspace outlined in the wireframe, ensuring testers can comfortably interact with the map and deduction logs simultaneously without visual fatigue.

* **Phase 3: Asymmetrical State Management & Testing Loops (The Experience)**
  * *Objective:* Implement role-based visibility rules, action logging, and session state persistence (including undo buffers).
  * *Business Value:* Enables seamless local testing cycles, allowing creators to rapidly simulate multiple game nights, audit rule balance, and refine gameplay dynamics.