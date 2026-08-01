#!/usr/bin/env bash
# Shared loader + validator for the Telegram control channel (#SDLC loop).
# Sourced by every telegram-*.sh so secrets live in ONE place: a gitignored .env
# (or the real environment), NEVER hardcoded in a script or committed.
#
# Required env:
#   TELEGRAM_BOT_TOKEN   - a FRESH token from @BotFather. If a token was ever
#                          pasted into a shared file/chat, treat it as burned:
#                          /revoke it in BotFather and mint a new one.
#   TELEGRAM_CHAT_ID     - the owner's numeric chat id. Inbound is allow-listed
#                          to exactly this id; every other sender is ignored.
#   TELEGRAM_CMD_SECRET  - a shared secret every COMMAND must carry. Defence in
#                          depth: even if the bot token leaks, no one can drive
#                          the loop without this too.
set -euo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$_here/.env" ] && set -a && . "$_here/.env" && set +a

: "${TELEGRAM_BOT_TOKEN:?set TELEGRAM_BOT_TOKEN (fresh BotFather token, in .env)}"
: "${TELEGRAM_CHAT_ID:?set TELEGRAM_CHAT_ID (owner numeric chat id, in .env)}"

# chat id must be a bare integer — it is interpolated into a jq filter, so a
# non-numeric value is rejected rather than trusted.
case "$TELEGRAM_CHAT_ID" in
  ''|*[!0-9-]*) echo "TELEGRAM_CHAT_ID must be numeric" >&2; exit 2 ;;
esac

API="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
