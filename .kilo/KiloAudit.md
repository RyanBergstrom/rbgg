# Agent Session Retro & Bottleneck Audit

## Objective

Analyze my recent coding agent sessions, task transcripts, and recent Git diffs to identify recurring failure modes, thrashing loops, and workflow bottlenecks—then generate concrete, minimal rule updates to prevent them in future runs.

## Inputs to Inspect

Gather and cross-reference the following evidence before drawing conclusions:

1. **Recent Session Transcripts / History:** Review the last 10–15 non-trivial tasks (or query the local Kilo Code session database / exported transcripts), paying closest attention to sessions with high turn counts, retries, tool errors, or manual user corrections.
2. **Recent Git History & Diffs:** Run `git log -n 20 --stat` and inspect commits where the same files were modified repeatedly or reverted across consecutive tasks.
3. **Existing Agent Instructions:** Read any existing project instruction files (e.g., `.kilocode/rules/`, `AGENTS.md`, `CLAUDE.md`, or custom mode definitions) so you do not suggest rules that already exist.

## Failure Taxonomy (Tag Every Friction Event)

Classify every stall, mistake, or manual rescue into one of these categories:

- **[CONTEXT-DRIFT]**: Missed existing project conventions, edited the wrong architectural layer, or lost track of constraints mid-task.
- **[BLIND-EDITING]**: Modified multiple files or guessed at fixes before reproducing the issue or running a targeted check/test.
- **[RETRY-LOOP]**: Repeated the same failing command, edit, or hypothesis 2+ times without isolating the root cause.
- **[OVER-ENGINEERING]**: Introduced unrequested abstractions, broad refactors, or unnecessary file churn.
- **[ENV-TOOL-FRICTION]**: Command timeouts, wrong shell/path assumptions, missing environment variables, or slow feedback loops.
- **[VERIFICATION-GAP]**: Claimed completion while leaving edge cases, type errors, regressions, or untested paths behind.

## Analysis Rules

- **Cite concrete evidence:** Every identified bottleneck must reference specific sessions, files, commands, or commit hashes. Do not generalize without examples.
- **Separate symptoms from root causes:** Distinguish between _what broke_ (e.g., "test failed three times") and _why the agent stalled_ (e.g., "agent edited implementation before inspecting the test fixture schema").
- **Prioritize by time/token cost:** Rank patterns by how much wall-clock time, turn count, or rework they actually cost.
- **Keep proposed rules surgical:** Do not write a bloated 50-rule manifesto. Propose only high-leverage rules that directly address the top 3–5 recurring patterns.

## Required Output Format

### 1. Executive Scorecard

- **Sessions Audited:** [Count & date/commit range]
- **Top 3 Time/Turn Sinks:** [Ranked list with estimated frequency]
- **Most Affected Files / Subsystems:** [Paths where thrashing occurred most]

### 2. Recurring Failure Patterns (Ranked by Impact)

For each top pattern, provide:

- **Pattern Name & Tag:** e.g., `Repeated Blind Edits on Parser Edge Cases [BLIND-EDITING]`
- **Frequency:** X of Y sessions
- **Evidence:** Specific session IDs/titles, file paths, and what happened
- **Root Cause:** Why the agent defaulted to this behavior
- **Preventative Lever:** Whether this is best fixed via a rule, a verification command, or mode delegation (`Plan` → `Code` → `Debug`)

### 3. Ready-to-Inject Instruction Patches

Provide exact, copy-pasteable Markdown rules formatted for `.kilocode/rules/` or `AGENTS.md`, grouped by:

- **Pre-Edit / Planning Rules** (what the agent must check before touching code)
- **Execution & Retry Circuit Breakers** (when to stop and change strategy)
- **Definition of Done / Verification Gates** (what must pass before finishing)

### 4. Workflow & Mode Adjustments

Recommend 2–3 specific adjustments to how I use Kilo Code modes (`Plan`, `Code`, `Debug`, or custom modes) or fast verification scripts based on the bottlenecks found.
