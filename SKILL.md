# SKILL: Fixing Errors Workflow

## Name
Fixing Errors (bug-hunting and resolution)

## Description
A workspace-scoped skill that guides an agent through a reproducible, test-driven process to find, isolate, and fix runtime and logic errors. Designed to eliminate errors thoroughly (manga xatolarni bartarafa qilmanga muakml bolgan).

## Scope
- Workspace-scoped (default). Can be adapted for personal use.
- Focus: Python backend, tests, linters, and minimal CI checks present in the repo.

## Goals / Quality Criteria
- The bug is reproducible and a minimal reproduction is created.
- A minimal, correct fix is implemented with unit/integration tests added or updated.
- All tests pass and static checks (linters, type checks) do not regress.
- Changes are small, well-scoped, and documented.

## Step-by-step Process
1. Gather context
   - Reproduce the error locally (run failing test, reproduce runtime steps).
   - Collect relevant logs, stack traces, failing test names, and exact commands.
2. Reproduce and isolate
   - Create a minimal reproducer (small failing test or script) that demonstrates the bug.
   - If reproduction fails, ask for more info (inputs, env, exact steps).
3. Hypothesize
   - Read related files and tests. Form one or more hypotheses about the root cause.
   - Identify the likely code area and dependencies.
4. Experiment safely
   - Add temporary assertions, logs, or small instrumentation to confirm hypotheses.
   - Run the focused test(s) or reproducer iteratively.
5. Implement fix
   - Make the smallest code change that addresses the root cause.
   - Prefer adding tests first (test-driven) or adding a regression test alongside the fix.
6. Validate
   - Run the full test suite and linters: ensure no regressions.
   - Check for performance or security regressions if relevant.
7. Document and propose
   - Add a concise commit message describing root cause and fix.
   - Update docs or comments as needed.
8. Iterate
   - If tests still fail, revert the minimal change, reevaluate hypotheses, and repeat.

## Decision Points
- Cannot reproduce: ask for exact steps, environment, seed values, or a failing test case.
- Hypothesis invalidated by logs/experiments: back to step 3 and try alternate hypotheses.
- Fix causes new failures: revert and write a more precise test to guard behavior.

## Automation & Agent Capabilities
When invoked, the agent should attempt these actions (if permitted):
- Run selected tests (`pytest tests/unit path/to/test::test_name`).
- Run linters (`flake8`, `ruff`, or configured tools).
- Open and inspect project files referenced by stack traces.
- Propose patches and apply small `apply_patch` edits.
- Add or update tests in `tests/unit` or `tests/integration`.

## Completion Checks
- All added/changed tests pass locally.
- No new lint or static-analysis errors introduced.
- A self-contained commit or patch exists that explains the change.

## Example Prompts (English)
- "Reproduce and fix failing unit test `tests/unit/test_services.py::test_xyz` — add regression test and minimal fix."
- "I see a KeyError in `database/models.py` stack trace — find root cause and propose a patch."

## Example Prompts (Uzbek)
- "`tests/unit/test_services.py::test_xyz` unit-testidagi xatoni takrorla va tuzat, regressiya testini qo'sh."
- "`database/models.py` da KeyError bor — sababini top va patch taklif qil."

## Clarifying Questions (to present when needed)
- Is this skill workspace-scoped or personal for your account?
- Which language do you prefer for prompts and messages (English / Uzbek)?
- Any CI or environment constraints (Docker, specific Python version, secrets) the agent must respect?

## Iteration Plan
1. Draft this SKILL.md and save to workspace (done).
2. Ask the user the clarifying questions above.
3. Update the SKILL.md with any preferences and finalize.
4. Optionally create a companion `skill-prompts.md` with ready-to-run prompts.

## Notes
- Keep fixes minimal and test-driven.
- Prefer asking for missing runtime details rather than guessing.
- If a fix touches many files, request a code-review step.

---
Saved by an assistant draft. Please confirm scope and language preferences to finalize the skill.