# GitHub Copilot Instructions for rbgg

---

## MANDATORY: Session Startup Sequence

**Do this immediately on your very first response in every session. Do NOT wait for the user to ask. Do NOT skip steps.**

### Step 1: Read these files (all are required, do them in order)

1. **`AGENTS.md`** (already auto-attached — review it)
2. **`sessionhandoff.md`** — This is the previous session's handoff. It contains exactly what was done, what's left, and what to do next.
3. **`work-items.md`** — Check what work items exist and their status.

### Step 2: Acknowledge the handoff

After reading the files above, confirm to the user:
- What the previous session accomplished
- What the next steps are
- That you're ready to continue

### Step 3: Verify environment

- Run `python -m pytest -v` in `/api` to confirm all tests pass (expected: 71/72 with 1 pre-existing failure)
- Check if the API server is running if relevant to the task

**If the user just says "hello" or something similar, still perform Steps 1-3 above before responding.**

---

## Project Reference

Read and follow closely the directions in `AGENTS.md` for project structure, architecture, and coding conventions.

---

## Logoff / Session End

When the user says **"logoff"**, **"wrap up"**, **"end session"**, **"bye"**, or similar phrases, perform these steps **in order**:

1. Read **`logoff.md`** for the full handoff process
2. Archive current session documentation to **`documentation/sessions/`**
3. Update **`AGENTS.md`** with any changes from this session
4. Update **`work-items.md`** with any new or completed work items
5. Create a new **`sessionhandoff.md`** documenting:
   - What was accomplished this session
   - Key changes made (files modified, functions changed)
   - Test results (how many pass/fail, what's new)
   - Next steps for the following session
   - A "Prompt for Next Session" block the user can paste into a new session
6. Inform the user they're safe to log off

---

## General Rules

- Always run tests before and after making changes
- Keep `AGENTS.md` updated with any new patterns, files, or conventions discovered
- Use the existing MCTS and game architecture — don't reinvent what's already built
- Lost Cities is the primary game; Checkers is secondary/stubbed
- Backend tests: `pytest` in `/api`. Frontend tests: `vitest` in `/web`
