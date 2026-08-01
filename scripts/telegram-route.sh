#!/usr/bin/env bash
# Map an owner message to a FIXED command token. Two hard rules keep this from
# being a remote-shell backdoor:
#   1. Every command must carry TELEGRAM_CMD_SECRET as its first argument — so a
#      leaked bot token alone cannot drive the loop.
#   2. The message is only ever matched against a closed verb set; its payload is
#      emitted as DATA (RUN:<task>) for the agent loop to treat as a task string.
#      It is never eval'd or passed to a shell.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/telegram-env.sh"
: "${TELEGRAM_CMD_SECRET:?set TELEGRAM_CMD_SECRET (shared command secret, in .env)}"

CMD="$("$(dirname "${BASH_SOURCE[0]}")/telegram-command.sh")"
[ -z "$CMD" ] && { echo "NONE"; exit 0; }

# <verb> <secret> [payload...]
read -r verb tok rest <<< "$CMD"
if [ "${tok:-}" != "$TELEGRAM_CMD_SECRET" ]; then
  echo "NONE"; exit 0                      # missing/wrong secret -> ignored silently
fi

case "$verb" in
  /status)   echo "STATUS" ;;
  /run)      echo "RUN:${rest}" ;;
  /continue) echo "CONTINUE" ;;
  /pause)    echo "PAUSE" ;;
  /reset)    echo "RESET" ;;
  *)         echo "NONE" ;;
esac
