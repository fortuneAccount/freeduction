#!/usr/bin/env bash
set -e

echo "Installing dependencies..."
sudo apt-get update -y
sudo apt-get install -y xvfb x11vnc fluxbox websockify novnc  libegl1 libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-render-util0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libx11-xcb1 libxcb1 libxcb-glx0 libxcb-shm0 libxcb-sync1 libxcb-xfixes0 libxcb-shape0 libxcb-randr0 libxcb-render-util0 libxcb-render0 libxcb-xkb1 libxkbcommon-x11-0

pip uninstall -y PyQt5 PyQt5-sip PySide2
pip install PyQt6 nltk requests beautifulsoup4 configparser psutil pygame

echo "Starting virtual display..."
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1
fluxbox &

echo "Starting VNC server..."
x11vnc -display :1 -nopw -forever -shared -rfbport 5900 &

echo "Starting noVNC on port 6080..."
websockify --web=/usr/share/novnc 6080 localhost:5900 &

echo ""
echo "GUI environment is ready!"
echo "Go to the Ports tab, set port 6080 to Public, and open the link." 
