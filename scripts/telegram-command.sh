#!/usr/bin/env bash
# Poll getUpdates and return the latest message text FROM THE OWNER CHAT ONLY.
# Messages from any other chat id are dropped here — the allow-list is the first
# gate (trustworthy because the bot token is a secret; Telegram sets the real
# sender chat id server-side, a caller cannot forge it).
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/telegram-env.sh"

OFFSET_FILE="${TMPDIR:-/tmp}/telegram_offset_${TELEGRAM_CHAT_ID}"
[ -f "$OFFSET_FILE" ] || echo 0 > "$OFFSET_FILE"
OFFSET="$(cat "$OFFSET_FILE")"

RESP="$(curl -s "${API}/getUpdates?offset=${OFFSET}&timeout=1")"

# Advance the offset past everything we just read, so each update is handled once.
NEW="$(echo "$RESP" | jq -r '.result[-1].update_id // empty')"
[ -n "$NEW" ] && echo $((NEW + 1)) > "$OFFSET_FILE"

# Latest text from the allow-listed chat only.
echo "$RESP" | jq -r --argjson owner "$TELEGRAM_CHAT_ID" \
  '.result[] | select(.message.chat.id == $owner) | .message.text // empty' | tail -1
