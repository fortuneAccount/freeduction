#!/usr/bin/env bash
set -e

echo "Installing VNC/XFCE dependencies..."

sudo apt-get update

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tigervnc-standalone-server \
    tigervnc-common \
    tigervnc-tools \
    xfce4 \
    xfce4-goodies \
    dbus-x11 \
    websockify \
    xterm \
    libegl1 \
    libx11-xcb1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libgl1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libfontconfig1

echo "Installing noVNC..."

if [ ! -d /opt/novnc ]; then
    sudo git clone --depth 1 https://github.com/novnc/noVNC.git /opt/novnc
fi

if [ ! -e /opt/novnc/index.html ]; then
    sudo ln -s /opt/novnc/vnc.html /opt/novnc/index.html
fi

mkdir -p "$HOME/.vnc"

cat > "$HOME/.vnc/xstartup" <<'EOF'
#!/bin/sh

unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS

export XDG_CURRENT_DESKTOP=XFCE
export XDG_SESSION_DESKTOP=xfce
export XDG_CONFIG_DIRS=/etc/xdg/xdg-xfce:/etc/xdg/xdg-xfce:/etc/xdg

exec dbus-run-session -- startxfce4
EOF

chmod +x "$HOME/.vnc/xstartup"

echo
echo "VNC setup complete."
echo
echo "VNC password authentication is disabled for this local development setup."
