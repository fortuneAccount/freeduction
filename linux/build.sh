#!/usr/bin/env bash
set -e

ENV_NAME="anattagen-build"

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

pyenv activate $ENV_NAME

echo "Cleaning old build artifacts..."
rm -rf build dist

echo "Running PyInstaller..."
pyinstaller anattagen.spec --clean --noconfirm

echo "=============================="
echo " BUILD SUCCESS"
echo " Output: dist/anattagen"
echo "=============================="

