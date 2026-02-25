@echo off
REM Launcher.bat - Game Launcher Batch Script
REM A Windows batch script port of the Launcher functionality

setlocal enabledelayedexpansion

REM ===== INITIALIZATION =====
set "HOME=%~dp0.."
set "BINHOME=%HOME%\bin"
set "CURPIDF=%HOME%\rjpids.ini"
set "LOGFILE=%HOME%\launcher.log"
set "PLINK=%~1"

REM Initialize log
echo [%date% %time%] Launcher started. Home directory: %HOME% > "%LOGFILE%"

REM Check if target was provided
if "%PLINK%"=="" (
    echo No target specified. Usage: Launcher.bat ^<target^>
    echo [%date% %time%] ERROR: No target specified >> "%LOGFILE%"
    timeout /t 3 >nul
    exit /b 1
)

echo Launching: %PLINK%
echo [%date% %time%] Launching: %PLINK% >> "%LOGFILE%"

REM ===== PARSE TARGET =====
for %%F in ("%PLINK%") do (
    set "SCPATH=%%~dpF"
    set "SCEXTN=%%~xF"
    set "GAMENAME=%%~nF"
)

REM Remove trailing backslash from SCPATH
if "%SCPATH:~-1%"=="\" set "SCPATH=%SCPATH:~0,-1%"

REM ===== LOAD CONFIGURATION =====
set "GAMEINI=%SCPATH%\Game.ini"
if not exist "%GAMEINI%" set "GAMEINI=%HOME%\config.ini"

if not exist "%GAMEINI%" (
    echo Configuration file not found
    echo [%date% %time%] ERROR: Configuration file not found >> "%LOGFILE%"
    timeout /t 3 >nul
    exit /b 1
)

echo Loading configuration from: %GAMEINI%
echo [%date% %time%] Loading configuration from: %GAMEINI% >> "%LOGFILE%"

REM Parse INI file - Game section
call :ReadINI "%GAMEINI%" "Game" "Executable" GAMEPATH
call :ReadINI "%GAMEINI%" "Game" "Directory" GAMEDIR
call :ReadINI "%GAMEINI%" "Game" "Name" GAMENAME_INI
call :ReadINI "%GAMEINI%" "Game" "IsoPath" ISOPATH

REM Parse INI file - Options section
call :ReadINI "%GAMEINI%" "Options" "RunAsAdmin" RUNASADMIN
call :ReadINI "%GAMEINI%" "Options" "HideTaskbar" HIDETASKBAR
call :ReadINI "%GAMEINI%" "Options" "UseKillList" USEKILLLIST
call :ReadINI "%GAMEINI%" "Options" "KillList" KILLLIST
call :ReadINI "%GAMEINI%" "Options" "TerminateBorderlessOnExit" TERMBORDERLESS

REM Parse INI file - Paths section
call :ReadINI "%GAMEINI%" "Paths" "ControllerMapperApp" MAPPERAPP
call :ReadINI "%GAMEINI%" "Paths" "ControllerMapperOptions" MAPPEROPTS
call :ReadINI "%GAMEINI%" "Paths" "ControllerMapperArguments" MAPPERARGS
call :ReadINI "%GAMEINI%" "Paths" "BorderlessWindowingApp" BORDERLESSAPP
call :ReadINI "%GAMEINI%" "Paths" "BorderlessWindowingOptions" BORDERLESSOPTS
call :ReadINI "%GAMEINI%" "Paths" "BorderlessWindowingArguments" BORDERLESSARGS
call :ReadINI "%GAMEINI%" "Paths" "MultiMonitorTool" MMTOOL
call :ReadINI "%GAMEINI%" "Paths" "MultiMonitorOptions" MMOPTS
call :ReadINI "%GAMEINI%" "Paths" "MultiMonitorArguments" MMARGS
call :ReadINI "%GAMEINI%" "Paths" "MultiMonitorGamingConfig" MMGAMECONFIG
call :ReadINI "%GAMEINI%" "Paths" "MultiMonitorDesktopConfig" MMDESKTOPCONFIG
call :ReadINI "%GAMEINI%" "Paths" "DiscMountApp" MOUNTAPP
call :ReadINI "%GAMEINI%" "Paths" "DiscMountOptions" MOUNTOPTS
call :ReadINI "%GAMEINI%" "Paths" "DiscMountArguments" MOUNTARGS
call :ReadINI "%GAMEINI%" "Paths" "DiscUnmountApp" UNMOUNTAPP
call :ReadINI "%GAMEINI%" "Paths" "DiscUnmountOptions" UNMOUNTOPTS
call :ReadINI "%GAMEINI%" "Paths" "DiscUnmountArguments" UNMOUNTARGS

REM Parse INI file - CloudSync section
call :ReadINI "%GAMEINI%" "CloudSync" "Enabled" CLOUDENABLED
call :ReadINI "%GAMEINI%" "CloudSync" "App" CLOUDAPP
call :ReadINI "%GAMEINI%" "CloudSync" "Options" CLOUDOPTS
call :ReadINI "%GAMEINI%" "CloudSync" "Arguments" CLOUDARGS
call :ReadINI "%GAMEINI%" "CloudSync" "Wait" CLOUDWAIT
call :ReadINI "%GAMEINI%" "CloudSync" "BackupOnLaunch" CLOUDBACKUPONLAUNCH
call :ReadINI "%GAMEINI%" "CloudSync" "UploadOnExit" CLOUDUPLOADONEXIT

REM Parse INI file - LocalBackup section
call :ReadINI "%GAMEINI%" "LocalBackup" "Enabled" BACKUPENABLED
call :ReadINI "%GAMEINI%" "LocalBackup" "App" BACKUPAPP
call :ReadINI "%GAMEINI%" "LocalBackup" "Options" BACKUPOPTS
call :ReadINI "%GAMEINI%" "LocalBackup" "Arguments" BACKUPARGS
call :ReadINI "%GAMEINI%" "LocalBackup" "Wait" BACKUPWAIT
call :ReadINI "%GAMEINI%" "LocalBackup" "BackupOnLaunch" BACKUPBACKUPONLAUNCH
call :ReadINI "%GAMEINI%" "LocalBackup" "BackupOnExit" BACKUPBACKUPONEXIT

REM Parse INI file - PreLaunch section
call :ReadINI "%GAMEINI%" "PreLaunch" "App1" PREAPP1
call :ReadINI "%GAMEINI%" "PreLaunch" "App1Options" PREAPP1OPTS
call :ReadINI "%GAMEINI%" "PreLaunch" "App1Arguments" PREAPP1ARGS
call :ReadINI "%GAMEINI%" "PreLaunch" "App1Wait" PREAPP1WAIT
call :ReadINI "%GAMEINI%" "PreLaunch" "App2" PREAPP2
call :ReadINI "%GAMEINI%" "PreLaunch" "App2Options" PREAPP2OPTS
call :ReadINI "%GAMEINI%" "PreLaunch" "App2Arguments" PREAPP2ARGS
call :ReadINI "%GAMEINI%" "PreLaunch" "App2Wait" PREAPP2WAIT
call :ReadINI "%GAMEINI%" "PreLaunch" "App3" PREAPP3
call :ReadINI "%GAMEINI%" "PreLaunch" "App3Options" PREAPP3OPTS
call :ReadINI "%GAMEINI%" "PreLaunch" "App3Arguments" PREAPP3ARGS
call :ReadINI "%GAMEINI%" "PreLaunch" "App3Wait" PREAPP3WAIT

REM Parse INI file - PostLaunch section
call :ReadINI "%GAMEINI%" "PostLaunch" "App1" POSTAPP1
call :ReadINI "%GAMEINI%" "PostLaunch" "App1Options" POSTAPP1OPTS
call :ReadINI "%GAMEINI%" "PostLaunch" "App1Arguments" POSTAPP1ARGS
call :ReadINI "%GAMEINI%" "PostLaunch" "App1Wait" POSTAPP1WAIT
call :ReadINI "%GAMEINI%" "PostLaunch" "App2" POSTAPP2
call :ReadINI "%GAMEINI%" "PostLaunch" "App2Options" POSTAPP2OPTS
call :ReadINI "%GAMEINI%" "PostLaunch" "App2Arguments" POSTAPP2ARGS
call :ReadINI "%GAMEINI%" "PostLaunch" "App2Wait" POSTAPP2WAIT
call :ReadINI "%GAMEINI%" "PostLaunch" "App3" POSTAPP3
call :ReadINI "%GAMEINI%" "PostLaunch" "App3Options" POSTAPP3OPTS
call :ReadINI "%GAMEINI%" "PostLaunch" "App3Arguments" POSTAPP3ARGS
call :ReadINI "%GAMEINI%" "PostLaunch" "App3Wait" POSTAPP3WAIT
call :ReadINI "%GAMEINI%" "PostLaunch" "JustAfterLaunchApp" JUSTAFTERAPP
call :ReadINI "%GAMEINI%" "PostLaunch" "JustAfterLaunchOptions" JUSTAFTEROPTS
call :ReadINI "%GAMEINI%" "PostLaunch" "JustAfterLaunchArguments" JUSTAFTERARGS
call :ReadINI "%GAMEINI%" "PostLaunch" "JustAfterLaunchWait" JUSTAFTERWAIT
call :ReadINI "%GAMEINI%" "PostLaunch" "JustBeforeExitApp" JUSTBEFOREAPP
call :ReadINI "%GAMEINI%" "PostLaunch" "JustBeforeExitOptions" JUSTBEFOREOPTS
call :ReadINI "%GAMEINI%" "PostLaunch" "JustBeforeExitArguments" JUSTBEFOREARGS
call :ReadINI "%GAMEINI%" "PostLaunch" "JustBeforeExitWait" JUSTBEFOREWAIT

REM Parse INI file - Sequences section
call :ReadINI "%GAMEINI%" "Sequences" "LaunchSequence" LAUNCHSEQ
call :ReadINI "%GAMEINI%" "Sequences" "ExitSequence" EXITSEQ

REM Set default sequences if not specified
if "%LAUNCHSEQ%"=="" set "LAUNCHSEQ=Cloud-Sync,Local-Backup,Controller-Mapper,Monitor-Config,No-TB,mount-disc,Pre1,Pre2,Pre3,Borderless"
if "%EXITSEQ%"=="" set "EXITSEQ=Post1,Post2,Post3,Unmount-disc,Monitor-Config,Taskbar,Controller-Mapper,Local-Backup,Cloud-Sync"

REM Override GAMENAME if found in INI
if not "%GAMENAME_INI%"=="" set "GAMENAME=%GAMENAME_INI%"

REM Default GAMEPATH to PLINK if not set
if "%GAMEPATH%"=="" set "GAMEPATH=%PLINK%"

REM Default GAMEDIR to directory of GAMEPATH
if "%GAMEDIR%"=="" (
    for %%F in ("%GAMEPATH%") do set "GAMEDIR=%%~dpF"
    if "!GAMEDIR:~-1!"=="\" set "GAMEDIR=!GAMEDIR:~0,-1!"
)

echo Game: %GAMENAME%
echo Path: %GAMEPATH%
echo Directory: %GAMEDIR%
echo [%date% %time%] Game: %GAMENAME%, Path: %GAMEPATH%, Dir: %GAMEDIR% >> "%LOGFILE%"

REM ===== EXECUTE LAUNCH SEQUENCE =====
echo Executing launch sequence: %LAUNCHSEQ%
echo [%date% %time%] Executing launch sequence: %LAUNCHSEQ% >> "%LOGFILE%"

for %%S in (%LAUNCHSEQ%) do (
    call :ExecuteSequenceItem "%%S" "launch"
)

REM ===== LAUNCH GAME =====
echo Launching game: %GAMENAME%
echo [%date% %time%] Launching game: %GAMENAME% >> "%LOGFILE%"

cd /d "%GAMEDIR%"

if /i "%RUNASADMIN%"=="1" (
    echo Running as administrator...
    echo [%date% %time%] Running as administrator >> "%LOGFILE%"
    powershell -Command "Start-Process '%GAMEPATH%' -Verb RunAs -Wait" 2>>"%LOGFILE%"
) else (
    start "" /wait "%GAMEPATH%"
)

echo Game exited
echo [%date% %time%] Game exited >> "%LOGFILE%"

REM ===== JUST BEFORE EXIT APP =====
if not "%JUSTBEFOREAPP%"=="" (
    echo Running Just Before Exit app...
    echo [%date% %time%] Running Just Before Exit app: %JUSTBEFOREAPP% >> "%LOGFILE%"
    call :RunApp "%JUSTBEFOREAPP%" "%JUSTBEFOREOPTS%" "%JUSTBEFOREARGS%" "%JUSTBEFOREWAIT%"
)

REM ===== EXECUTE EXIT SEQUENCE =====
echo Executing exit sequence: %EXITSEQ%
echo [%date% %time%] Executing exit sequence: %EXITSEQ% >> "%LOGFILE%"

for %%S in (%EXITSEQ%) do (
    call :ExecuteSequenceItem "%%S" "exit"
)

REM ===== KILL PROCESSES FROM KILL LIST =====
if /i "%USEKILLLIST%"=="1" (
    if not "%KILLLIST%"=="" (
        echo Killing processes from kill list...
        echo [%date% %time%] Killing processes from kill list: %KILLLIST% >> "%LOGFILE%"
        for %%P in (%KILLLIST%) do (
            echo   Killing: %%P
            taskkill /F /IM "%%P" >nul 2>&1
        )
    )
)

echo Launcher finished
echo [%date% %time%] Launcher finished >> "%LOGFILE%"
exit /b 0

REM ===== HELPER FUNCTIONS =====

:ExecuteSequenceItem
REM Execute a single sequence item
set "Item=%~1"
set "Phase=%~2"

echo   Sequence: %Item%
echo [%date% %time%]   Sequence: %Item% >> "%LOGFILE%"

if /i "%Item%"=="Controller-Mapper" (
    if "%Phase%"=="launch" (
        if not "%MAPPERAPP%"=="" (
            echo     Starting Controller Mapper...
            call :RunApp "%MAPPERAPP%" "%MAPPEROPTS%" "%MAPPERARGS%" "0"
        )
    ) else (
        if not "%MAPPERAPP%"=="" (
            echo     Stopping Controller Mapper...
            for %%F in ("%MAPPERAPP%") do taskkill /F /IM "%%~nxF" >nul 2>&1
        )
    )
)

if /i "%Item%"=="Monitor-Config" (
    if "%Phase%"=="launch" (
        if not "%MMTOOL%"=="" if not "%MMGAMECONFIG%"=="" (
            echo     Applying gaming monitor config...
            call :RunApp "%MMTOOL%" "%MMOPTS%" "/LoadConfig "%MMGAMECONFIG%"" "1"
        )
    ) else (
        if not "%MMTOOL%"=="" if not "%MMDESKTOPCONFIG%"=="" (
            echo     Restoring desktop monitor config...
            call :RunApp "%MMTOOL%" "%MMOPTS%" "/LoadConfig "%MMDESKTOPCONFIG%"" "1"
        )
    )
)

if /i "%Item%"=="No-TB" (
    if /i "%HIDETASKBAR%"=="1" (
        echo     Hiding taskbar...
        powershell -WindowStyle Hidden -Command "$p = (New-Object -ComObject Shell.Application).NameSpace(0x0); $p.Self.InvokeVerb('Hide')" 2>nul
    )
)

if /i "%Item%"=="Taskbar" (
    if /i "%HIDETASKBAR%"=="1" (
        echo     Showing taskbar...
        powershell -WindowStyle Hidden -Command "$p = (New-Object -ComObject Shell.Application).NameSpace(0x0); $p.Self.InvokeVerb('Show')" 2>nul
    )
)

if /i "%Item%"=="mount-disc" (
    if not "%MOUNTAPP%"=="" if not "%ISOPATH%"=="" (
        echo     Mounting disc: %ISOPATH%...
        call :RunApp "%MOUNTAPP%" "%MOUNTOPTS%" ""%ISOPATH%" %MOUNTARGS%" "1"
    )
)

if /i "%Item%"=="Unmount-disc" (
    if not "%UNMOUNTAPP%"=="" if not "%ISOPATH%"=="" (
        echo     Unmounting disc...
        call :RunApp "%UNMOUNTAPP%" "%UNMOUNTOPTS%" ""%ISOPATH%" %UNMOUNTARGS%" "1"
    )
)

if /i "%Item%"=="Borderless" (
    if not "%BORDERLESSAPP%"=="" (
        echo     Starting Borderless Gaming...
        call :RunApp "%BORDERLESSAPP%" "%BORDERLESSOPTS%" "%BORDERLESSARGS%" "0"
    )
)

if /i "%Item%"=="Pre1" (
    if not "%PREAPP1%"=="" (
        echo     Running Pre-Launch App 1...
        call :RunApp "%PREAPP1%" "%PREAPP1OPTS%" "%PREAPP1ARGS%" "%PREAPP1WAIT%"
    )
)

if /i "%Item%"=="Pre2" (
    if not "%PREAPP2%"=="" (
        echo     Running Pre-Launch App 2...
        call :RunApp "%PREAPP2%" "%PREAPP2OPTS%" "%PREAPP2ARGS%" "%PREAPP2WAIT%"
    )
)

if /i "%Item%"=="Pre3" (
    if not "%PREAPP3%"=="" (
        echo     Running Pre-Launch App 3...
        call :RunApp "%PREAPP3%" "%PREAPP3OPTS%" "%PREAPP3ARGS%" "%PREAPP3WAIT%"
    )
)

if /i "%Item%"=="Post1" (
    if not "%POSTAPP1%"=="" (
        echo     Running Post-Launch App 1...
        call :RunApp "%POSTAPP1%" "%POSTAPP1OPTS%" "%POSTAPP1ARGS%" "%POSTAPP1WAIT%"
    )
)

if /i "%Item%"=="Post2" (
    if not "%POSTAPP2%"=="" (
        echo     Running Post-Launch App 2...
        call :RunApp "%POSTAPP2%" "%POSTAPP2OPTS%" "%POSTAPP2ARGS%" "%POSTAPP2WAIT%"
    )
)

if /i "%Item%"=="Post3" (
    if not "%POSTAPP3%"=="" (
        echo     Running Post-Launch App 3...
        call :RunApp "%POSTAPP3%" "%POSTAPP3OPTS%" "%POSTAPP3ARGS%" "%POSTAPP3WAIT%"
    )
)

if /i "%Item%"=="Cloud-Sync" (
    if /i "%CLOUDENABLED%"=="1" (
        if "%Phase%"=="launch" (
            if /i "%CLOUDBACKUPONLAUNCH%"=="1" (
                if not "%CLOUDAPP%"=="" (
                    echo     Running Cloud Sync (download)...
                    call :RunApp "%CLOUDAPP%" "%CLOUDOPTS%" "%CLOUDARGS%" "%CLOUDWAIT%"
                )
            )
        ) else (
            if /i "%CLOUDUPLOADONEXIT%"=="1" (
                if not "%CLOUDAPP%"=="" (
                    echo     Running Cloud Sync (upload)...
                    call :RunApp "%CLOUDAPP%" "%CLOUDOPTS%" "%CLOUDARGS%" "%CLOUDWAIT%"
                )
            )
        )
    )
)

if /i "%Item%"=="Local-Backup" (
    if /i "%BACKUPENABLED%"=="1" (
        if "%Phase%"=="launch" (
            if /i "%BACKUPBACKUPONLAUNCH%"=="1" (
                if not "%BACKUPAPP%"=="" (
                    echo     Running Local Backup (pre-launch)...
                    call :RunApp "%BACKUPAPP%" "%BACKUPOPTS%" "%BACKUPARGS%" "%BACKUPWAIT%"
                )
            )
        ) else (
            if /i "%BACKUPBACKUPONEXIT%"=="1" (
                if not "%BACKUPAPP%"=="" (
                    echo     Running Local Backup (post-exit)...
                    call :RunApp "%BACKUPAPP%" "%BACKUPOPTS%" "%BACKUPARGS%" "%BACKUPWAIT%"
                )
            )
        )
    )
)

goto :eof

:RunApp
REM Run an application with options and arguments
set "AppPath=%~1"
set "AppOpts=%~2"
set "AppArgs=%~3"
set "AppWait=%~4"

if "%AppPath%"=="" goto :eof

set "FullCmd=%AppPath%"
if not "%AppOpts%"=="" set "FullCmd=%FullCmd% %AppOpts%"
if not "%AppArgs%"=="" set "FullCmd=%FullCmd% %AppArgs%"

echo [%date% %time%]     Executing: %FullCmd% >> "%LOGFILE%"

if /i "%AppWait%"=="1" (
    start "" /wait %FullCmd% 2>>"%LOGFILE%"
) else (
    start "" %FullCmd% 2>>"%LOGFILE%"
)

goto :eof

:ReadINI
REM Usage: call :ReadINI "filepath" "section" "key" ReturnVariable
set "INIFile=%~1"
set "Section=%~2"
set "Key=%~3"
set "Value="

for /f "usebackq tokens=1,* delims==" %%A in ("%INIFile%") do (
    set "Line=%%A"
    set "LineValue=%%B"
    
    REM Check if we're in the right section
    if "!Line:~0,1!"=="[" (
        set "Line=!Line:[=!"
        set "Line=!Line:]=!"
        if /i "!Line!"=="%Section%" set "InSection=1"
        if /i not "!Line!"=="%Section%" set "InSection=0"
    )
    
    REM If in section and key matches, get value
    if defined InSection if "!InSection!"=="1" (
        if /i "!Line!"=="%Key%" (
            set "Value=!LineValue!"
            REM Trim leading/trailing spaces
            for /f "tokens=* delims= " %%V in ("!Value!") do set "Value=%%V"
        )
    )
)

set "%~4=%Value%"
goto :eof
