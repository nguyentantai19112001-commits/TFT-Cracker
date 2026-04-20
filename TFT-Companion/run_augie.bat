@echo off
setlocal

:: Auto-elevate to admin so `keyboard` can capture global hotkeys.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
title Augie
echo ============================================================
echo   Launching Augie...
echo ============================================================
py assistant_overlay.py

echo.
echo ============================================================
echo   Augie exited. Press any key to close this window.
echo ============================================================
pause >nul
