#!/bin/sh
set -eu

MODE="auto"

if [ "${1:-}" = "--linux" ]; then
    MODE="linux"
elif [ "${1:-}" = "--windows" ]; then
    MODE="windows"
fi

# Detect OS for auto mode or cross-compilation hints
OS_NAME=$(uname -s)

# ---------- toolchain selection ----------

if [ "$MODE" = "windows" ]; then
    OUT=launcher.exe
    # Note: -mwindows must come first, then libraries in dependency order
    LDFLAGS="-mwindows -lgdi32 -luser32 -lshell32 -lshlwapi -lole32 -lpsapi -ladvapi32 -lcomctl32"
    # If on Linux, use cross-compiler
    if [ "$OS_NAME" = "Linux" ]; then
        CC=${CC:-x86_64-w64-mingw32-gcc}
    else
        CC=${CC:-gcc}
    fi
elif [ "$MODE" = "linux" ]; then
    CC=${CC:-gcc}
    OUT=launcher
    LDFLAGS=""
else
    # auto
    CC=${CC:-gcc}
    OUT=launcher
    LDFLAGS=""
fi

# ---------- flags (locked, reproducible) ----------

CFLAGS="
-std=c11
-O2
-Wall
-Wextra
-Wpedantic
-fno-omit-frame-pointer
-fno-ident
-ffile-prefix-map=$(pwd)=.
"

# ---------- build ----------

echo "Compiler : $CC"
echo "Output   : $OUT"

$CC $CFLAGS \
    launcher.c \
    tray_menu.c \
    config_editor.c \
    inih/ini.c \
    -o $OUT \
    $LDFLAGS

echo "Built $OUT"
