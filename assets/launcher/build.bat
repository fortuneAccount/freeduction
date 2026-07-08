@echo off
setlocal enabledelayedexpansion

REM Always run from this script's directory (so ./build.sh is found regardless
REM of the caller's current working directory).
cd /d "%~dp0"
REM =========================================================================
REM  build.bat - Windows build script for the C launcher (mirror of build.sh)
REM  Output of every step is captured to %TEMP%\build\build.log
REM =========================================================================

REM Set DEBUG=1 for verbose troubleshooting (logged to console + build.log)
set "DEBUG=1"

set "LOGFILE=%TEMP%\build\build.log"
if not exist "%TEMP%\build" mkdir "%TEMP%\build"
REM Start a fresh log for this run
type nul > "%LOGFILE%"

call :dbg "DEBUG mode ON"
call :dbg "LOGFILE = %LOGFILE%"
call :dbg "OS = %OS%  ARCH = %PROCESSOR_ARCHITECTURE%  PROCESSOR = %PROCESSOR_IDENTIFIER%"
call :dbg "CD = %CD%"
call :dbg "PATH = %PATH%"

REM Resolve Program Files paths at top level (their names contain a ')'
set "PF86=%ProgramFiles(x86)%"
set "PF=%ProgramFiles%"

set "OUT=Launcher.exe"
set "SRC=launcher.c tray_menu.c config_editor.c inih\ini.c"

call :log "=== Launcher build started %DATE% %TIME% ==="
call :log "Source files: %SRC%"

REM -------------------------------------------------------------------------
REM  Toolchain detection
REM -------------------------------------------------------------------------
set "MSYSROOT="
set "MSYSARCH="
set "CC="
set "MODE="

REM 1) MSYS2 install (preferred). We build INSIDE its shell so gcc/ld can
REM    resolve their runtime DLLs (libgcc, libwinpthread, msys-2.0, ...).
call :dbg "--- detecting MSYS2 ---"
for %%R in (C:\msys64 C:\msys2 C:\msys32) do (
    if not defined MSYSROOT (
        if exist "%%~R\usr\bin\bash.exe" (
            for %%A in (mingw64 ucrt64 clang64 mingw32) do (
                if not defined MSYSARCH (
                    if exist "%%~R\%%A\bin\gcc.exe" (
                        set "MSYSROOT=%%~R"
                        set "MSYSARCH=%%A"
                    )
                )
            )
            if not defined MSYSARCH (
                if exist "%%~R\usr\bin\gcc.exe" (
                    set "MSYSROOT=%%~R"
                    set "MSYSARCH=msys"
                )
            )
        )
    )
)
if defined MSYSROOT (
    call :dbg "MSYS2 found: root=!MSYSROOT! arch=!MSYSARCH!"
) else (
    call :dbg "MSYS2 not found under C:\msys64 / C:\msys2 / C:\msys32"
)

REM 2) Microsoft Visual C++ (via vswhere) - fallback when no MSYS2
if not defined MSYSROOT (
    if not defined CC (
        call :dbg "--- checking MSVC via vswhere ---"
        call :dbg "PF86=[!PF86!] PF=[!PF!]"
        set "VSWHERE=!PF86!\Microsoft Visual Studio\Installer\vswhere.exe"
        if not exist "!VSWHERE!" set "VSWHERE=!PF!\Microsoft Visual Studio\Installer\vswhere.exe"
        call :dbg "VSWHERE=[!VSWHERE!]"
        if exist "!VSWHERE!" (
            "!VSWHERE!" -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find "**\vcvars64.bat" > "%TEMP%\build\_vc.txt" 2>&1
            set "VCVARS="
            for /f "usebackq delims=" %%i in ("%TEMP%\build\_vc.txt") do (
                if not defined VCVARS set "VCVARS=%%i"
            )
            del /q "%TEMP%\build\_vc.txt" 2>nul
            if defined VCVARS (
                call :log "Found MSVC vcvars: !VCVARS!"
                call "!VCVARS!" >nul 2>&1
                where cl >nul 2>&1
                if !errorlevel! == 0 (
                    call :verify_msvc && (
                        set "CC=cl"
                        set "MODE=msvc"
                        call :log "Using cl (MSVC)"
                    ) || call :log "cl present but cannot compile (broken toolchain?)"
                ) else (
                    call :log "vcvars did not place cl on PATH"
                )
            ) else (
                call :log "vswhere found no MSVC VC.Tools component"
            )
        ) else (
            call :log "vswhere not found"
        )
    )
)

if not defined MSYSROOT (
    if not defined CC (
        call :log "ERROR: no working toolchain found (MSYS2 or MSVC)."
        call :log "  - Install MSYS2 and a MinGW-w64 toolchain (pacman -S mingw-w64-x86_64-gcc), or"
        call :log "  - Install Visual Studio with the 'Desktop development with C++' workload."
        call :log "=== Launcher build FAILED %TIME% ==="
        exit /b 1
    )
)

REM -------------------------------------------------------------------------
REM  Compile
REM -------------------------------------------------------------------------
if defined MSYSROOT (
    REM Build inside the MSYS2 shell so gcc/ld can resolve their runtime DLLs.
    if "!MSYSARCH!" == "mingw64" set "MSYSTEM=MINGW64"
    if "!MSYSARCH!" == "ucrt64"  set "MSYSTEM=UCRT64"
    if "!MSYSARCH!" == "clang64" set "MSYSTEM=CLANG64"
    if "!MSYSARCH!" == "mingw32" set "MSYSTEM=MINGW32"
    if "!MSYSARCH!" == "msys"    set "MSYSTEM=MSYS"
    call :dbg "MSYSTEM=!MSYSTEM!"

    set "BASH=!MSYSROOT!\usr\bin\bash.exe"
    "!MSYSROOT!\usr\bin\cygpath.exe" -u "%CD%" > "%TEMP%\build\_cyg.txt" 2>nul
    set /p UNIXDIR=<"%TEMP%\build\_cyg.txt"
    del /q "%TEMP%\build\_cyg.txt" 2>nul
    call :dbg "UNIXDIR = !UNIXDIR!"

    call :log "Building via MSYS2 shell (!MSYSARCH!): bash ./build.sh --windows"
    call :run "!BASH!" -lc "cd '!UNIXDIR!' && bash ./build.sh --windows"
) else (
    set "CLFLAGS=/std:c11 /O2 /W4 /nologo /D_CRT_SECURE_NO_WARNINGS"
    set "LIBS=user32.lib shell32.lib shlwapi.lib ole32.lib psapi.lib advapi32.lib gdi32.lib comctl32.lib"
    set "LINKFLAGS=/SUBSYSTEM:WINDOWS"
    call :log "Compiler : cl.exe"
    call :log "Output   : %OUT%"
    call :run cl.exe %CLFLAGS% %SRC% %LIBS% /link %LINKFLAGS% /OUT:%OUT%
)

if not !errorlevel! == 0 (
    call :log "=== Launcher build FAILED %TIME% ==="
    exit /b 1
)

REM build.sh writes "launcher.exe" (lowercase); normalize to Launcher.exe
if exist launcher.exe (
    if not exist "%OUT%" ren launcher.exe "%OUT%"
)

if exist "%OUT%" (
    call :log "Built %OUT%"
    call :log "=== Launcher build SUCCEEDED %TIME% ==="
    exit /b 0
) else (
    call :log "ERROR: %OUT% was not produced"
    call :log "=== Launcher build FAILED %TIME% ==="
    exit /b 1
)

REM -------------------------------------------------------------------------
REM  Subroutines
REM -------------------------------------------------------------------------
:dbg
    if "%DEBUG%" == "1" echo [DBG] %*
    echo [DBG] %* >> "%LOGFILE%"
    goto :eof

:log
    echo %*
    echo %* >> "%LOGFILE%"
    goto :eof

:run
    call :log "> %*"
    %* > "%TEMP%\build\_out.tmp" 2>&1
    set "RC=%ERRORLEVEL%"
    type "%TEMP%\build\_out.tmp"
    type "%TEMP%\build\_out.tmp" >> "%LOGFILE%"
    del /q "%TEMP%\build\_out.tmp" 2>nul
    exit /b %RC%

:verify_msvc
    call :dbg "verify_msvc: testing cl"
    > "%TEMP%\build\_t.c" echo int main(void){return 0;}
    cl "%TEMP%\build\_t.c" /Fe:"%TEMP%\build\_t.exe" > "%TEMP%\build\_t.out" 2>&1
    set "TRC=%ERRORLEVEL%"
    call :dbg "verify_msvc: rc=!TRC!"
    if "%DEBUG%" == "1" (
        call :dbg "  cl test output:"
        type "%TEMP%\build\_t.out"
        type "%TEMP%\build\_t.out" >> "%LOGFILE%"
    )
    del /q "%TEMP%\build\_t.c" "%TEMP%\build\_t.exe" "%TEMP%\build\_t.out" 2>nul
    exit /b %TRC%
