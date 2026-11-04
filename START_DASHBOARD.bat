@echo off
title Smart Fire Dashboard
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo Python was not found on this computer.
  echo Install it from python.org and tick "Add Python to PATH".
  pause
  exit /b
)

echo Checking libraries (first time can take a minute)...
%PY% -m pip install --quiet pyserial matplotlib

echo.
echo IMPORTANT: close the Arduino IDE Serial Monitor first.
echo Starting dashboard...
%PY% dashboard.py
pause
