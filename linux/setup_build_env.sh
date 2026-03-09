#!/usr/bin/env bash
set -e

ENV_NAME="anattagen-build"
PYTHON_VERSION="3.11.9"

echo "=============================="
echo " Anattagen Linux Setup"
echo " Python $PYTHON_VERSION + Qt6"
echo "=============================="

# ---- System deps ----
sudo apt update
sudo apt install -y \
  build-essential \
  curl git \
  libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev \
  libncursesw5-dev xz-utils tk-dev \
  libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
  qt6-base-dev qt6-base-dev-tools python3-pyqt6

# ---- pyenv ----
if [ ! -d "$HOME/.pyenv" ]; then
  curl https://pyenv.run | bash
fi

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# ---- Python ----
pyenv install -s $PYTHON_VERSION
pyenv virtualenv -f $PYTHON_VERSION $ENV_NAME
pyenv activate $ENV_NAME

# ---- Python deps ----
pip install --upgrade pip setuptools wheel
pip install pyinstaller

if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  pip install py7zr nltk requests beautifulsoup4 configparser psutil pygame
fi

echo "=============================="
echo " Setup COMPLETE"
echo " Activate with:"
echo "   pyenv activate $ENV_NAME"
echo "=============================="

