#!/usr/bin/env bash
# Switch which AI the bank uses. Takes effect on the next request - no restart.
#
#   ./ai.sh              which one is on now
#   ./ai.sh claude       Claude, on your Claude plan (no API key)
#   ./ai.sh openai       OpenAI, on the key in .env
#   ./ai.sh claude-api   Claude, on an Anthropic API key
#   ./ai.sh off          no AI

set -euo pipefail
cd "$(dirname "$0")/backend"
exec uv run --quiet python -m scripts.ai "$@"
