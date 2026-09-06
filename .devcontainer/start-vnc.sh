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
    -localhost

# Start noVNC/websockify.
websockify \
    --web=/opt/novnc \
    6080 \
    localhost:5901 \
    >/tmp/novnc.log 2>&1 &

echo "VNC started:"
echo "  DISPLAY=$DISPLAY"
echo "  VNC:   localhost:5901"
echo "  noVNC: http://localhost:6080/vnc.html"
