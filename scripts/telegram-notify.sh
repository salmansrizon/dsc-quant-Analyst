#!/usr/bin/env bash
# Send-only notification to the owner chat. No inbound, no command execution —
# the low-risk half of the channel.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/telegram-env.sh"

curl -s -X POST "${API}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=🔔 ${1:-}" >/dev/null
