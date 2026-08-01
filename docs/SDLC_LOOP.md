# SDLC loop — Telegram control channel

Two-way control of the SDLC loop from Telegram, hardened so it is **not** a
remote-shell backdoor. All abilities are preserved: `/status`, `/run`,
`/continue`, `/pause`, `/reset`.

## Security model

| Risk | Mitigation |
|------|------------|
| Token in a shared file → public | Secrets live only in a gitignored `.env` (or the real env). No token in any script. `.env.example` is the template. |
| Anyone messaging the bot controls the machine | Inbound is **allow-listed to the owner `chat_id`**; every other sender is dropped (`telegram-command.sh`). |
| Leaked token still commands the loop | Every command must carry a **shared secret** as its first arg (`telegram-route.sh`). Token alone is not enough. |
| Arbitrary shell from a message | Messages match a **fixed verb set** only; a `RUN` payload is a task *string* for the skill layer, never `eval`'d or shelled. |
| Unattended promotion to `main` | Planning opens a **PR and pauses**; the loop resumes only after the owner merges and sends `/continue`. Budget/retry caps and `/reset` confirmation stay. |

## One-time setup

1. **Revoke the exposed token.** Any token pasted into a shared skill/chat is
   burned — in @BotFather run `/revoke` for that bot, then `/token` for a fresh one.
2. `cp .env.example .env` and fill in:
   - `TELEGRAM_BOT_TOKEN` — the fresh token.
   - `TELEGRAM_CMD_SECRET` — any long random string you choose.
3. **Get your chat id:** message the bot once, then:
   ```bash
   source scripts/telegram-env.sh && curl -s "$API/getUpdates" | jq '.result[-1].message.chat.id'
   ```
   Put the number in `.env` as `TELEGRAM_CHAT_ID`.
4. Smoke-test send-only: `./scripts/telegram-notify.sh "control channel up"`.

## Commands

All commands take the secret as the first argument:

| Message | Action |
|---------|--------|
| `/status <secret>` | current phase / completed / failures |
| `/run <secret> <task>` | start/resume the loop on a task |
| `/continue <secret>` | resume after a paused PR gate |
| `/pause <secret>` | pause and save state |
| `/reset <secret>` then `/reset <secret> CONFIRM` | wipe loop state |

Start it: `./start_loop.sh "Continue the wayfinder map #84."`

## Caveat

`loops/loop_engine.py` `run_skill()` is a **simulation stub** — it fakes the
evidence gates. Wire it to real skill invocations (wayfinder/tdd/code-review/…)
before trusting the automated phase transitions. The control channel, state
persistence, notifications, and human PR gate are real.
