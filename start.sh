#!/bin/bash
# Start both the API server and dashboard dev server

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================"
echo "  Momentum Scanner — Starting"
echo "================================"

# Start Flask API
echo "Starting API server on :5001..."
cd "$DIR"
source .venv/bin/activate
python api.py &
API_PID=$!

# Start Vite dev server
echo "Starting dashboard on :5173..."
cd "$DIR/dashboard"
npm run dev &
VITE_PID=$!

echo ""
echo "  API:       http://localhost:5001"
echo "  Dashboard: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $API_PID $VITE_PID 2>/dev/null; exit" INT TERM
wait
