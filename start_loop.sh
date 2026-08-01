#!/usr/bin/env bash
# Launch the SDLC loop with the Telegram control channel. Validates that all
# secrets are present (from .env) before starting; never contains secrets itself.
set -euo pipefail
cd "$(dirname "$0")"
. scripts/telegram-env.sh                       # fails loud if token/chat missing
: "${TELEGRAM_CMD_SECRET:?set TELEGRAM_CMD_SECRET in .env}"
export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_CMD_SECRET
exec python3 loops/loop_engine.py "${1:-Continue the wayfinder map #84.}"
