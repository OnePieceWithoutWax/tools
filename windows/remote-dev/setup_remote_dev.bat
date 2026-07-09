@echo off
:: setup_remote_dev.bat
:: Launches the remote dev setup PowerShell script as Administrator

:: Check if already running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run the PowerShell script from the same directory as this .bat file
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_remote_dev.ps1"

echo.
pause