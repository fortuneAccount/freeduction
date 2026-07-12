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

REM Parse INI file - Launcher section
call :ReadINI "%GAMEINI%" "Launcher" "RunAsAdmin" RUNASADMIN
call :ReadINI "%GAMEINI%" "Launcher" "HideTaskbar" HIDETASKBAR
call :ReadINI "%GAMEINI%" "Launcher" "Borderless" BORDERLESS
call :ReadINI "%GAMEINI%" "Launcher" "UseKillList" USEKILLLIST
call :ReadINI "%GAMEINI%" "Launcher" "KillList" KILLLIST
call :ReadINI "%GAMEINI%" "Launcher" "TerminateBorderlessOnExit" TERMBORDERLESS

REM Parse INI file - mapperprofiles section
call :ReadINI "%GAMEINI%" "mapperprofiles" "player1profile" PLAYER1PROFILE
call :ReadINI "%GAMEINI%" "mapperprofiles" "player2profile" PLAYER2PROFILE
call :ReadINI "%GAMEINI%" "mapperprofiles" "deskprofile" DESKPROFILE

REM Parse INI file - monitorcfgs section
call :ReadINI "%GAMEINI%" "monitorcfgs" "monitorgamingcfg" MONGAMECONFIG
call :ReadINI "%GAMEINI%" "monitorcfgs" "monitordeskcfg" MONDESKCONFIG

REM Backward compatibility: old Profiles section
if "%PLAYER1PROFILE%"=="" call :ReadINI "%GAMEINI%" "Profiles" "Player1Profile" PLAYER1PROFILE
if "%PLAYER2PROFILE%"=="" call :ReadINI "%GAMEINI%" "Profiles" "Player2Profile" PLAYER2PROFILE
if "%DESKPROFILE%"=="" call :ReadINI "%GAMEINI%" "Profiles" "DeskProfile" DESKPROFILE
if "%MONGAMECONFIG%"=="" call :ReadINI "%GAMEINI%" "Profiles" "MonitorGamingConfig" MONGAMECONFIG
if "%MONDESKCONFIG%"=="" call :ReadINI "%GAMEINI%" "Profiles" "MonitorDeskConfig" MONDESKCONFIG

REM Parse INI file - ControllerMapper section
call :ReadINI "%GAMEINI%" "ControllerMapper" "ControllerMapperPath" MAPPERAPP
call :ReadINI "%GAMEINI%" "ControllerMapper" "ControllerMapperPathOptions" MAPPEROPTS
call :ReadINI "%GAMEINI%" "ControllerMapper" "ControllerMapperPathArguments" MAPPERARGS

REM Parse INI file - BorderlessWindowing section
call :ReadINI "%GAMEINI%" "BorderlessWindowing" "BorderlessWindowingPath" BORDERLESSAPP
call :ReadINI "%GAMEINI%" "BorderlessWindowing" "BorderlessWindowingPathOptions" BORDERLESSOPTS
call :ReadINI "%GAMEINI%" "BorderlessWindowing" "BorderlessWindowingPathArguments" BORDERLESSARGS

REM Parse INI file - Monitor section
call :ReadINI "%GAMEINI%" "Monitor" "monitorapppath" MONTOOL
call :ReadINI "%GAMEINI%" "Monitor" "monitorapppathoptions" MONOPTS
call :ReadINI "%GAMEINI%" "Monitor" "monitorapppatharguments" MONARGS

REM Parse INI file - DiscDrivePrefs section
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "EnableDiscMountCfg" MOUNTENABLED
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscMountCfgPath" MOUNTCFGAPP
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscMountCfgPathOptions" MOUNTCFGOPTS
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscMountCfgPathArguments" MOUNTCFARGS
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "EnableDiscUnmountCfg" UNMOUNTENABLED
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscUnmountCfgPath" UNMOUNTCFGAPP
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscUnmountCfgPathOptions" UNMOUNTCFGOPTS
call :ReadINI "%GAMEINI%" "DiscDrivePrefs" "DiscUnmountCfgPathArguments" UNMOUNTCFARGS

REM Backward compatibility: old DiscMountCfg/DiscUnmountCfg sections
if "%MOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscMountCfg" "EnableDiscMountCfg" MOUNTENABLED
if "%MOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscMountCfg" "DiscMountCfgPath" MOUNTCFGAPP
if "%MOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscMountCfg" "DiscMountCfgPathOptions" MOUNTCFGOPTS
if "%MOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscMountCfg" "DiscMountCfgPathArguments" MOUNTCFARGS
if "%UNMOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscUnmountCfg" "EnableDiscUnmountCfg" UNMOUNTENABLED
if "%UNMOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscUnmountCfg" "DiscUnmountCfgPath" UNMOUNTCFGAPP
if "%UNMOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscUnmountCfg" "DiscUnmountCfgPathOptions" UNMOUNTCFGOPTS
if "%UNMOUNTCFGAPP%"=="" call :ReadINI "%GAMEINI%" "DiscUnmountCfg" "DiscUnmountCfgPathArguments" UNMOUNTCFARGS

REM Parse INI file - CloudSync section
call :ReadINI "%GAMEINI%" "CloudSync" "EnableCloudSync" CLOUDENABLED
call :ReadINI "%GAMEINI%" "CloudSync" "CloudSyncPath" CLOUDAPP
call :ReadINI "%GAMEINI%" "CloudSync" "CloudSyncPathOptions" CLOUDOPTS
call :ReadINI "%GAMEINI%" "CloudSync" "CloudSyncPathArguments" CLOUDARGS
call :ReadINI "%GAMEINI%" "CloudSync" "CloudSyncPathRunWait" CLOUDWAIT
call :ReadINI "%GAMEINI%" "CloudSync" "RemoteName" CLOUDREMOTENAME
call :ReadINI "%GAMEINI%" "CloudSync" "UserPrefix" CLOUDUSERPREFIX
call :ReadINI "%GAMEINI%" "CloudSync" "SavePath" CLOUDSAVEPATH
call :ReadINI "%GAMEINI%" "CloudSync" "BackupOnLaunch" CLOUDBACKUPONLAUNCH
call :ReadINI "%GAMEINI%" "CloudSync" "UploadOnExit" CLOUDUPLOADONEXIT

REM Parse INI file - LocalBackup section
call :ReadINI "%GAMEINI%" "LocalBackup" "EnableLocalBackup" BACKUPENABLED
call :ReadINI "%GAMEINI%" "LocalBackup" "LocalBackupPath" BACKUPAPP
call :ReadINI "%GAMEINI%" "LocalBackup" "LocalBackupPathOptions" BACKUPOPTS
call :ReadINI "%GAMEINI%" "LocalBackup" "LocalBackupPathArguments" BACKUPARGS
call :ReadINI "%GAMEINI%" "LocalBackup" "LocalBackupPathRunWait" BACKUPWAIT
call :ReadINI "%GAMEINI%" "LocalBackup" "LocalPrefix" BACKUPLOCALPREFIX
call :ReadINI "%GAMEINI%" "LocalBackup" "SavePath" BACKUPSAVEPATH
call :ReadINI "%GAMEINI%" "LocalBackup" "MaxBackups" BACKUPMAXBACKUPS
call :ReadINI "%GAMEINI%" "LocalBackup" "BackupOnLaunch" BACKUPBACKUPONLAUNCH
call :ReadINI "%GAMEINI%" "LocalBackup" "BackupOnExit" BACKUPBACKUPONEXIT

REM Parse INI file - Pre1, Pre2, Pre3 sections
call :ReadINI "%GAMEINI%" "Pre1" "Pre1Path" PREAPP1
call :ReadINI "%GAMEINI%" "Pre1" "Pre1PathOptions" PREAPP1OPTS
call :ReadINI "%GAMEINI%" "Pre1" "Pre1PathArguments" PREAPP1ARGS
call :ReadINI "%GAMEINI%" "Pre1" "Pre1PathRunWait" PREAPP1WAIT
call :ReadINI "%GAMEINI%" "Pre2" "Pre2Path" PREAPP2
call :ReadINI "%GAMEINI%" "Pre2" "Pre2PathOptions" PREAPP2OPTS
call :ReadINI "%GAMEINI%" "Pre2" "Pre2PathArguments" PREAPP2ARGS
call :ReadINI "%GAMEINI%" "Pre2" "Pre2PathRunWait" PREAPP2WAIT
call :ReadINI "%GAMEINI%" "Pre3" "Pre3Path" PREAPP3
call :ReadINI "%GAMEINI%" "Pre3" "Pre3PathOptions" PREAPP3OPTS
call :ReadINI "%GAMEINI%" "Pre3" "Pre3PathArguments" PREAPP3ARGS
call :ReadINI "%GAMEINI%" "Pre3" "Pre3PathRunWait" PREAPP3WAIT

REM Parse INI file - Post1, Post2, Post3 sections
call :ReadINI "%GAMEINI%" "Post1" "Post1Path" POSTAPP1
call :ReadINI "%GAMEINI%" "Post1" "Post1PathOptions" POSTAPP1OPTS
call :ReadINI "%GAMEINI%" "Post1" "Post1PathArguments" POSTAPP1ARGS
call :ReadINI "%GAMEINI%" "Post1" "Post1PathRunWait" POSTAPP1WAIT
call :ReadINI "%GAMEINI%" "Post2" "Post2Path" POSTAPP2
call :ReadINI "%GAMEINI%" "Post2" "Post2PathOptions" POSTAPP2OPTS
call :ReadINI "%GAMEINI%" "Post2" "Post2PathArguments" POSTAPP2ARGS
call :ReadINI "%GAMEINI%" "Post2" "Post2PathRunWait" POSTAPP2WAIT
call :ReadINI "%GAMEINI%" "Post3" "Post3Path" POSTAPP3
call :ReadINI "%GAMEINI%" "Post3" "Post3PathOptions" POSTAPP3OPTS
call :ReadINI "%GAMEINI%" "Post3" "Post3PathArguments" POSTAPP3ARGS
call :ReadINI "%GAMEINI%" "Post3" "Post3PathRunWait" POSTAPP3WAIT

REM Parse INI file - JustAfterLaunch section
call :ReadINI "%GAMEINI%" "JustAfterLaunch" "Path" JUSTAFTERAPP
call :ReadINI "%GAMEINI%" "JustAfterLaunch" "PathOptions" JUSTAFTEROPTS
call :ReadINI "%GAMEINI%" "JustAfterLaunch" "PathArguments" JUSTAFTERARGS
call :ReadINI "%GAMEINI%" "JustAfterLaunch" "PathRunWait" JUSTAFTERWAIT

REM Parse INI file - JustBeforeExit section
call :ReadINI "%GAMEINI%" "JustBeforeExit" "Path" JUSTBEFOREAPP
call :ReadINI "%GAMEINI%" "JustBeforeExit" "PathOptions" JUSTBEFOREOPTS
call :ReadINI "%GAMEINI%" "JustBeforeExit" "PathArguments" JUSTBEFOREARGS
call :ReadINI "%GAMEINI%" "JustBeforeExit" "PathRunWait" JUSTBEFOREWAIT

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

REM ===== JUST AFTER LAUNCH APP =====
if not "%JUSTAFTERAPP%"=="" (
    echo Running Just After Launch app...
    echo [%date% %time%] Running Just After Launch app: %JUSTAFTERAPP% >> "%LOGFILE%"
    call :RunApp "%JUSTAFTERAPP%" "%JUSTAFTEROPTS%" "%JUSTAFTERARGS%" "%JUSTAFTERWAIT%"
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
        if not "%MONTOOL%"=="" if not "%MONGAMECONFIG%"=="" (
            echo     Applying gaming monitor config...
            call :RunApp "%MONTOOL%" "%MONOPTS%" "/LoadConfig "%MONGAMECONFIG%"" "1"
        )
    ) else (
        if not "%MONTOOL%"=="" if not "%MONDESKCONFIG%"=="" (
            echo     Restoring desktop monitor config...
            call :RunApp "%MONTOOL%" "%MONOPTS%" "/LoadConfig "%MONDESKCONFIG%"" "1"
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
        call :RunApp "%MOUNTAPP%" "%MOUNTOPTS%" ""%ISOPATH%" %MOUNTARGS%" "%MOUNTWAIT%"
    )
)

if /i "%Item%"=="Unmount-disc" (
    if not "%UNMOUNTAPP%"=="" if not "%ISOPATH%"=="" (
        echo     Unmounting disc...
        call :RunApp "%UNMOUNTAPP%" "%UNMOUNTOPTS%" ""%ISOPATH%" %UNMOUNTARGS%" "%UNMOUNTWAIT%"
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
