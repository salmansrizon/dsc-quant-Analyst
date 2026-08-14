---
name: autonomous-loop
description: Run the SDLC development loop autonomously inside THIS Claude Code session, driving the wayfinder map #84, reporting every milestone to Telegram. Use when the user wants hands-off development they can track from the Telegram app. Trigger: /autonomous-loop
---

# autonomous-loop

You (this session) ARE the loop runtime — there is no external engine. Drive the
wayfinder map, one ticket at a time, and narrate progress to Telegram so the user
can track it from their phone.

## Preconditions (check first, stop with a Telegram error if missing)
- `.env` has `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_CMD_SECRET`
  (see `docs/SDLC_LOOP.md`). Smoke-test: `./scripts/telegram-notify.sh "loop online"`.
- On `staging`, working tree clean, `gh auth status` ok.

## The loop
Repeat until a stop condition fires:

1. **Poll for a command** between tickets: `./scripts/telegram-route.sh`.
   - `PAUSE` → notify "⏸️ paused", stop.
   - `STATUS` → notify current ticket + counts, continue.
   - `RESET` → notify, do nothing destructive without an explicit `/reset <secret> CONFIRM`.
   - `RUN:<task>` → take `<task>` as the next objective instead of the frontier pick.
2. **Pick the next frontier ticket** on map #84: open child issues, unblocked
   (`issue_dependencies_summary.blocked_by == 0`), unassigned; first in map order.
   None left → notify "🎉 frontier clear on #84", stop.
3. **Classify it.** Only `research` / `task` / decided-implementation tickets are
   AFK. A `grilling` / `prototype` ticket needs the human — notify
   "🙋 #N <title> needs your input (HITL); loop pausing here" and STOP. Never
   self-answer a HITL ticket.
4. **Claim** it (`gh issue edit N --add-assignee @me`); notify "▶️ working #N <title>".
5. **Do the work** via the repo cadence:
   `/tdd` or implement → run the offline test suite → `/code-review` → fix
   blockers → commit → merge to `staging` → `/graphify` per issue. Notify the
   outcome of each heavy step ("✅ tests 5xx pass", "🔎 review clean", "📦 merged
   to staging").
6. **Record** the resolution on the ticket, update the map's Decisions-so-far,
   close the ticket. Notify "✔️ #N done". Back to step 1.

## Guardrails (non-negotiable)
- **Never merge to `main` unattended.** Promotion to main is a PR + a human
  `/continue`. Staging is the autonomous trunk.
- **Stop and notify** on: no frontier, a HITL ticket, `/pause`, red tests you
  can't green after a bounded try, or a merge conflict you can't cleanly resolve.
- One ticket in flight at a time. Keep each commit green (tests + typecheck/build).
- Report faithfully — if tests fail or a step is skipped, say so in the Telegram
  message, don't gloss.

## Telegram helper
Send any update with `./scripts/telegram-notify.sh "message"`. Keep messages one
line, prefixed with an emoji so they scan on a phone.

## Honest limit
Most of map #84's remaining frontier is HITL (design/grilling) or frontend
prototypes — the loop will advance the AFK tickets (research, decided
implementation, tasks) and pause for you on the rest. It is not a substitute for
the grilling sessions; it's a hands-off runner for the work that's already decided.
