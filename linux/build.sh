#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

ENV_NAME="app-build"

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

pyenv activate $ENV_NAME

"Cleaning old build artifacts..."
rm -rf ../build
rm -rf ../dist

echo "Running PyInstaller..."
pyinstaller app.spec --clean --noconfirm

echo "=============================="
echo " BUILD SUCCESS"
echo " Output: ../dist/app"
echo "=============================="

