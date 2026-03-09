@echo off
setlocal enabledelayedexpansion
for /f "delims=" %%a in ('echo."%CD%"') do (
	set "msystring=%%~a"
	set "msystring=!msystring:\=/!"
	set "clean=!msystring::=!"
	set "mstring=/!clean!"
)
for /f "delims=" %%a in ('cygpath -m /') do (
	if "%%~a" == "" (
			break
		 )
	set "cvtp=%%~a"
set "cvtp=!cvtp:/=\!"
	"!cvtp!msys2_shell.cmd" -defterm -mingw64 -shell bash -no-start -where "%CD%" -c '%mstring%/Build.sh --windows'
	
	REM !cvtp!msys2_shell.cmd" -defterm -here -no-start -mingw64 -shell bash -c "printenv"
	pause
)
pause