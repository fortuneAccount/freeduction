REM @echo off
setlocal enabledelayedexpansion

for /f "delims=" %%a in ('cygpath -m /') do (
	if "%%~a" == "" break
	set "MSYS2=%%~a"
	"%MSYS2%\msys2_shell.cmd"  -defterm -where "%CD%" -no-start -mingw64 -shell bash -c 'Build.sh --windows'
)
if "%MSYS2%" NEQ "" exit /b



if not defined VSCMD_VER (
	for /f "delims=" %%a in ('dir /b/a-d/s "%programfiles%\Microsoft Visual Studio\*vcvars64.bat"') do (
		set VSCMD_VER=%%~a -defterm -where "C:\users\jesse\documents\
github\freeduction" -no-start -mingw64
		break
	)
)
if not defined  -shell bash -c 'your_command_here'VSCMD_VER (
	for /f "delims=" %%a in ('dir /b/a-d/s "%programfiles% (x86)\Microsoft Visual Studio\*vcvars64.bat"') do (
		set VSCMD_VER=%%~a
		break
	)
					
)
if "%VSCMD%" NEQ "" goto VSCMD
if defined BUILD_TOOLS_ROOT (
	for /f "delims=;" %%j in ('echo "%BUILD_TOOLS_ROOT%"') do (
		pushd "%BUILD_TOOLS_ROOT%
		for /f "delims=" %%a in ('dir /b/a-d/s "vcvars64.bat"') do (
			set VSCMD_VER=%%~a
			popd
			break
		)
	if "%VSCMD_VER%" NEQ ""	break
	)
)
:VSCMD
call "%VSCMD_VER%" || exit /b 1
set CLFLAGS=/std:c11 /O2 /W4 /nologo /D_CRT_SECURE_NO_WARNINGS
set LIBS=user32.lib shell32.lib shlwapi.lib ole32.lib psapi.lib advapi32.lib gdi32.lib comctl32.lib comdlg32.lib
set LINKFLAGS=/SUBSYSTEM:WINDOWS /ENTRY:mainCRTStartup

cl.exe %CLFLAGS% launcher.c tray_menu.c config_editor.c inih\ini.c %LIBS% /link %LINKFLAGS%

if errorlevel 1 (
    echo Build failed
    exit /b 1
)

echo Build succeeded

move /y Launcher.exe ..\..\bin\Launcher.exe
