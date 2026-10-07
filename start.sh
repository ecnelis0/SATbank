#!/usr/bin/env bash
# Start the Mistake Bank: API on 8020, web on 3020.
#
# Run this from your own terminal. Started here, the servers belong to your
# window and live as long as it does — not to some other process that goes away.
#
#   ./start.sh          both halves
#   ./start.sh api      just the API
#   ./start.sh web      just the web server
#
# Ctrl-C stops whatever this started.

set -euo pipefail
cd "$(dirname "$0")"

# node is not on the default PATH on this machine; it lives in the aside runtime.
export PATH="$HOME/.aside/runtime/node/bin:$PATH"

API_PORT=8020
WEB_PORT=3020

alive() { curl -s -o /dev/null --max-time 2 "http://localhost:$1" 2>/dev/null; }

start_api() {
  if alive "$API_PORT/docs"; then
    echo "API already running on $API_PORT"
    return
  fi
  echo "Starting API on ${API_PORT}…"
  (cd backend && uv run uvicorn app.main:app --reload --port "$API_PORT") &
}

start_web() {
  if alive "$WEB_PORT"; then
    echo "Web already running on $WEB_PORT"
    return
  fi
  echo "Starting web on ${WEB_PORT}…"
  (cd frontend && NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" \
     npm run dev -- --port "$WEB_PORT") &
}

case "${1:-all}" in
  api) start_api ;;
  web) start_web ;;
  all) start_api; sleep 2; start_web ;;
  *) echo "usage: $0 [all|api|web]" >&2; exit 2 ;;
esac

echo
echo "  web  http://localhost:$WEB_PORT"
echo "  api  http://localhost:$API_PORT/docs"
echo "  Ctrl-C to stop."
wait
