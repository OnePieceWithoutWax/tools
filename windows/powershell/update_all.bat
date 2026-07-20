@echo off
:: update_all.bat
:: Thin wrapper: elevates to Administrator, then runs the update scripts in
:: order - PowerShell itself, help files, then Gallery modules - and
:: finally exports a module/profile inventory snapshot to the current
:: directory.
::
:: For a custom inventory output location, run export_module_inventory.ps1
:: directly with -OutputDirectory from an elevated PowerShell prompt.

:: Re-launch this file elevated if not already running as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_powershell.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_help.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_modules.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0export_module_inventory.ps1"

IF ERRORLEVEL 1 pause
