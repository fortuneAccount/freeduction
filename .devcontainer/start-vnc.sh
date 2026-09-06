#!/usr/bin/env bash
set -e

export DISPLAY=:1

# Stop stale processes from a previous container state.
vncserver -kill :1 >/dev/null 2>&1 || true
pkill -f "websockify.*6080" >/dev/null 2>&1 || true

# Start XFCE inside TigerVNC.
vncserver :1 \
    -geometry 1920x1080 \
    -depth 24 \
    -localhost \
    -IdleTimeout 0 \
    -MaxDisconnectionTime 0

# Start noVNC/websockify.
websockify \
    --web=/opt/novnc \
    --heartbeat=30 \
    --idle-timeout=0 \
    6080 \
    localhost:5901 \
    >/tmp/novnc.log 2>&1 &

echo "VNC started:"
echo "  DISPLAY=$DISPLAY"
echo "  VNC:   localhost:5901 (VNC clients only; do not open this port in a browser)"
echo "  noVNC: http://localhost:6080/vnc.html (open this forwarded port in a browser)"

if [ -n "${CODESPACE_NAME:-}" ]; then
    forwarding_domain="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
    echo "  URL:   https://${CODESPACE_NAME}-6080.${forwarding_domain}/vnc.html"
fi
