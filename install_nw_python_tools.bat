@echo off
:: install_python_tools.bat
:: Thin wrapper: installs every Python tool in this workspace globally via
:: uv, using --force so updates to a tool's source are always picked up.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_nw_python_tools.ps1"

IF ERRORLEVEL 1 pause
