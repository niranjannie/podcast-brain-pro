#!/bin/bash
# Start the Podcast Brain Pro backend (FastAPI + VibeVoice TTS)
#
# Bind to localhost by default: this service has no authentication, and /config
# returns masked API keys and lets a client overwrite them. Only set HOST=0.0.0.0
# on a network you trust.
set -e

cd "$(dirname "$0")"

if [ ! -f .venv/bin/activate ]; then
  echo "No virtualenv found. Create one first:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

# .env is read by the app itself (env_loader), so keys in voice-service/.env work
# whether you start through this script or call uvicorn directly.

echo "🚀 Starting Podcast Brain Pro backend..."
echo "   Address: http://$HOST:$PORT"
echo "   Health:  http://$HOST:$PORT/health"
echo ""

uvicorn main:app --host "$HOST" --port "$PORT" --workers 1
