#!/bin/bash
# Start the RADAR live pipeline server + public tunnel
# Run this from the RADAR project root

set -e

echo "=== Starting RADAR server ==="

# Kill any existing processes
pkill -f "radar_web.main" 2>/dev/null || true
pkill -f "serveo.net" 2>/dev/null || true
sleep 1

# Start the FastAPI server
echo "[1/3] Starting FastAPI server on port 8000..."
nohup python3 -m uvicorn radar_web.main:app --host 0.0.0.0 --port 8000 > /tmp/radar_server.log 2>&1 &
sleep 2

# Verify server is running
if ! curl -s --max-time 3 http://127.0.0.1:8000/ > /dev/null; then
  echo "ERROR: Server failed to start. Check /tmp/radar_server.log"
  exit 1
fi
echo "  Server running at http://localhost:8000"

# Start the serveo tunnel (auto-reconnects)
echo "[2/3] Starting public HTTPS tunnel..."
nohup sh -c '
while true; do
  ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -R 80:localhost:8000 serveo.net 2>&1
  sleep 10
done
' > /tmp/serveo.log 2>&1 &
sleep 8

# Get the tunnel URL
TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.serveousercontent\.com' /tmp/serveo.log | head -1)
if [ -z "$TUNNEL_URL" ]; then
  echo "WARNING: Could not get tunnel URL. Check /tmp/serveo.log"
else
  echo "  Tunnel URL: $TUNNEL_URL"
fi

echo ""
echo "[3/3] Updating frontend with tunnel URL..."
if [ -n "$TUNNEL_URL" ]; then
  sed -i '' "s|const PUBLIC_API_URL = 'https://[a-z0-9.-]*\.serveousercontent.com';|const PUBLIC_API_URL = '$TUNNEL_URL';|" index.html
  cp index.html docs/index.html
  echo "  index.html updated with $TUNNEL_URL"
  echo "  Run: git add index.html docs/index.html && git commit -m 'update tunnel URL' && git push origin main"
fi

echo ""
echo "=== RADAR is running! ==="
echo "  Local:    http://localhost:8000"
echo "  Public:   $TUNNEL_URL"
echo ""
echo "  To stop:  pkill -f 'radar_web.main' && pkill -f 'serveo.net'"
