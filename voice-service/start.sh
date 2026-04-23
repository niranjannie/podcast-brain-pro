#!/bin/bash
# Start the Podcast Brain Pro backend (FastAPI + VibeVoice TTS)

cd "$(dirname "$0")"
source .venv/bin/activate

PORT="${PORT:-8000}"

echo "🚀 Starting Podcast Brain Pro backend..."
echo "   Port: $PORT"
echo "   Health: http://localhost:$PORT/health"
echo ""

uvicorn main:app --host 0.0.0.0 --port "$PORT" --workers 1
