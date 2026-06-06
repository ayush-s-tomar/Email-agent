#!/bin/bash
# Quick start script — run from project root

set -e

echo "=== Email Agent Startup ==="

# Backend
echo "[1/2] Starting backend..."
cd backend
source .env 2>/dev/null || true

if [ ! -f "token.pickle" ]; then
  echo "No Google token found. Running OAuth flow..."
  python -c "from agent import get_google_credentials; get_google_credentials()"
fi

uvicorn server:app --port 8000 &
BACKEND_PID=$!
echo "Backend running on http://localhost:8000 (PID $BACKEND_PID)"

# Frontend
cd ../frontend
echo "[2/2] Starting frontend..."
npm run dev &
FRONTEND_PID=$!
echo "Dashboard running on http://localhost:5173 (PID $FRONTEND_PID)"

echo ""
echo "✓ Agent running. Open http://localhost:5173"
echo "  Press Ctrl+C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
