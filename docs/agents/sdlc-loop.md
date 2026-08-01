# SDLC loop

`loops/loop_engine.py` walks a task through `planning → spec → implement → review → maintain`,
invoking this repo's real skills from `.claude/skills/` and advancing only when a phase's
gate commands actually pass.

## Usage

```bash
./scripts/start_loop.sh "add a price-alert digest"   # start a new task
./scripts/start_loop.sh                              # resume the saved task
./scripts/start_loop.sh --status                     # print current state
./scripts/start_loop.sh --reset                      # clear saved state
```

## How a phase advances

Each phase runs its skills in order (`loops/loop_engine.py:PHASE_SKILLS`), feeding each
skill's output into the next as context. The phase then runs its gates
(`loops/gates.py:PHASE_GATES`) — real commands whose exit codes decide the outcome:

| Phase | Gates |
| ----- | ----- |
| `planning`, `spec`, `maintain` | none (judgement phases) |
| `implement` | working tree changed, `pytest -m "not integration"`, `npm run test:run`, `npm run lint` |
| `review` | `pytest -m "not integration"`, `npm run test:run` |

A phase passes only if every gate passes. **A skipped gate blocks** — if `node_modules` or
`pytest` is missing, the phase does not advance, so a missing toolchain escalates instead of
silently green-lighting the work. Run `npm ci` and install `requirements-dev.txt` before
expecting the `implement` or `review` phases to clear.

Each phase gets `MAX_ATTEMPTS_PER_PHASE` (3) attempts before the run escalates and exits
with a report.

## State

State persists to `memory/session/current.json` (gitignored — it is local run state, not
shared history). It records the task, current phase, per-phase attempt counts, accumulated
failures, and completed-issue count, so an interrupted run resumes where it left off.

## What the loop does not do

- **It never pushes or opens a pull request.** Publishing stays a human step, consistent
  with the GitHub Issues workflow in `issue-tracker.md`. There is no `staging` branch flow.
- It does not fabricate evidence. A phase's verdict comes from the gate commands' exit
  codes, not from parsing skill prose.

## Known environment gaps

- **`gh` CLI is not installed** in the remote session container, though
  `issue-tracker.md` documents `gh` for all issue operations. Use the GitHub MCP tools
  (`mcp__github__*`) for issue and PR work in that environment.
- **Telegram control is not wired up.** The `/initiate-project` skill specifies a two-way
  Telegram bot for `/status`, `/run`, `/continue`, `/pause`. `api.telegram.org` is blocked
  by this environment's egress policy (`CONNECT` returns 403), so it was deferred. The CLI
  subcommands above cover the same control surface locally; allowlisting
  `api.telegram.org` in the environment's network settings is the prerequisite for
  revisiting it.
