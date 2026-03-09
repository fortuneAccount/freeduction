@echo off
REM Universal unmount script - calls mount scripts with unmount flag
set "ISO=%~1"
set "BIN_DIR=%~dp0"

REM Try all available mount tools with unmount flag
if exist "%BIN_DIR%cdemu.cmd" (
    call "%BIN_DIR%cdemu.cmd" "%ISO%" --unmount
    exit /b %ERRORLEVEL%
)

REM Fallback to native PowerShell unmount
powershell -command "Dismount-DiskImage -ImagePath '%ISO%'" >nul 2>&1
exit /b %ERRORLEVEL%
