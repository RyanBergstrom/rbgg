# GitHub Copilot Instructions for rbgg

## 🛑 MANDATORY: Request-Saving Execution Constraints

You operate under a strict daily API request budget. Your primary directive is to compress workflows into the absolute minimum number of round-trip requests.

1. **Parallel Tooling & Pipelining:** NEVER execute tool calls sequentially if they can be grouped. When given a complex feature, bundle your file reads, edits, and validation commands into a single concurrent payload response.
2. **Single-Shot Edits:** Once you apply a code modification to a file, STOP execution immediately. Do not automatically compile, lint, or rerun tests unless explicitly instructed in the prompt.
3. **The Discovery Gate:** If you do not know the exact file path for a fix, limit yourself to a maximum of TWO (2) text search or grep queries. List the 3-5 candidate files you found, halt your execution, and ask the user: "Which of these files should we open?"
4. **Fast-Fail on Errors:** If a local build script, unit test target, or validation check returns a non-zero exit code (fails), STOP immediately. Do not attempt an autonomous auto-fix iteration loop.

## Session Startup Protocol

On your very first response of a session, do not waste requests running global tests or parsing logs.

1. Read `AGENTS.md` and `sessionhandoff.md` to capture project state.
2. Output a 3-bullet point summary identifying: (a) what was accomplished last turn, (b) the immediate file targets, and (c) a request for user confirmation to begin.

## Project Context Quick-Reference

- **Backend (`/api/`)**: Python 3.13, FastAPI, Uvicorn. Aligned with pytest targets.
- **Frontend (`/web/`)**: SvelteKit 2.70.3, Svelte 5, TypeScript. Aligned with Vitest targets.
- **Rule Engine Multipliers**: Lost Cities and Bus leverage pre-trained PPO model inferences. Twilight Struggle handles card actions via stage-isolated interactive choice matrices. Never mutate card dictionaries in-place.
- **Isolated Verification Targets Only**: Never run root `pytest` or complete repository test paths. Target individual verification via `pytest tests/test_filename.py` or isolated bash test hooks.
