# Project Agent Workflow & Guardrails

## 1. Pre-Edit Inspection & Single-Concern Edits

- **UI & CSS (`web/`):** Inspect the existing component structure, CSS rules, and rendered browser state _before_ editing layout, positioning, overflow, or `z-index`. Change **one layout concern per edit**—never guess dimensions across multiple properties at once.
- **Game Rules & Validator (`api/`):** Read the target rule logic and run the existing targeted tests _before_ modifying `validator.py` or turn-sequence code.
- **Keep Scope Tight:** Do not batch unrelated CSS, backend logic, and test refactors into a single pass.

## 2. Negative-Test-First for Game Invariants

- Whenever adding or modifying legal-move checks, command-pool costs, or turn/activation restrictions (`get_legal_moves`, `validate_move`), write or update a **negative unit test** proving the disallowed case is rejected alongside the valid case.

## 3. Execution & Retry Circuit Breakers

- **Two-Strike Rule:** If the same hypothesis or edit approach fails **twice** on a test, layout bug, or API mismatch, stop editing immediately. Switch to isolating a minimal reproduction (or `Debug` mode) before making further code changes.
- **No Scratch Files:** Do not create `_tmp_*.py` or ad-hoc debug scripts on disk. Use targeted `pytest` cases or inline expressions for diagnosis, and remove any temporary `console.log` / debug prints before finishing.

## 4. Shell & Dev Server Lifecycle

- Account for **PowerShell** syntax when running local Windows commands.
- Start long-lived processes (`uvicorn`, Vite dev server) using the **background process** tool—never run blocking servers in the foreground.

## 5. Definition of Done (Verification Gates)

Before claiming a task complete:

- **Backend (`api/`):** Targeted tests pass cleanly:
  ```powershell
  cd api; python -m pytest tests/test_fields_of_fire.py tests/test_fof_turn_sequence.py -q
  ```
