@echo off
REM K305 Newsense vs Ouster dashboard - Windows start file. Double-click it in File Explorer.
REM First start: creates a private Python environment in this folder (.venv) and installs the requirements (needs internet, 2-5 min).
setlocal
cd /d "%~dp0"
title K305 Newsense vs Ouster dashboard
echo === K305 Newsense vs Ouster dashboard ===

if exist ".venv\Scripts\python.exe" goto :haveenv

REM 1. find Python 3.11+ (the "py" launcher from python.org first)
set "PY="
for %%V in (3.12 3.11 3.13) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3.11 or newer is not installed.
  echo Please install Python 3.12 from https://www.python.org/downloads/
  echo IMPORTANT: tick "Add python.exe to PATH" in the installer. Then double-click this file again.
  start "" "https://www.python.org/downloads/windows/"
  goto :fail
)

REM 2. private environment in .venv (created once)
echo First start: creating the Python environment (once) ...
%PY% -m venv .venv
if errorlevel 1 (
  echo Could not create the environment.
  goto :fail
)

:haveenv
fc /b requirements.txt .venv\requirements.installed >nul 2>&1
if errorlevel 1 (
  echo Installing the required packages (once, needs internet, a few minutes^) ...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo Installing the packages failed. Check the internet connection and try again.
    goto :fail
  )
  copy /y requirements.txt .venv\requirements.installed >nul
)

REM 3. start (opens the browser automatically)
".venv\Scripts\python.exe" run_dashboard.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
pause
exit /b 1
