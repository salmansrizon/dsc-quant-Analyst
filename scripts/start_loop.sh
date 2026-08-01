#!/usr/bin/env bash
# Drive the SDLC loop. Usage:
#   ./scripts/start_loop.sh "add price alert digest"   # start a new task
#   ./scripts/start_loop.sh                            # resume saved task
#   ./scripts/start_loop.sh --status
#   ./scripts/start_loop.sh --reset
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 loops/loop_engine.py "$@"
