@echo off
rem mj launcher for Windows (cmd.exe / PowerShell).
rem
rem Windows commands are case-insensitive, so there is no way to ship both
rem "mj" and "MJ" like the Linux symlinks. This launcher recovers the typed
rem case from "%~0" (pure string ops - "%%~nxA" would hit the file system and
rem normalize the case) and appends --audio when you invoke it as MJ.
rem Everything else is forwarded as-is, so "mj --audio" always works too.
rem Keep this file ASCII-only: cmd reads .cmd files with the OEM code page.
setlocal
set "NAME=%~0"

:stripdir
if not "%NAME%"=="%NAME:*\=%" (
  set "NAME=%NAME:*\=%"
  goto stripdir
)

if /I "%NAME:~-4%"==".cmd" set "NAME=%NAME:~0,-4%"
set "SCRIPT=%~dp0mj"

where python >nul 2>nul
if errorlevel 1 goto use_py

if "%NAME%"=="MJ" (
  python "%SCRIPT%" --audio %*
) else (
  python "%SCRIPT%" %*
)
goto :eof

:use_py
if "%NAME%"=="MJ" (
  py -3 "%SCRIPT%" --audio %*
) else (
  py -3 "%SCRIPT%" %*
)
