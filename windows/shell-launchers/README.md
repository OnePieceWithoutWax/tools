# shell-launchers

"Open a shell here" `.bat` files — drop one into a folder (or invoke from Explorer's address bar) to open that shell in the current directory.

- `open_cmd_here.bat` — opens cmd.exe in the current directory (green-on-black)
- `open_git_bash_here.bat` — opens Git Bash in the current directory
- `open_git_bash_venv_here.bat` — opens Git Bash in the current directory and auto-activates `.venv` if one exists
- `open_powershell_here.bat` — opens PowerShell in the current directory

**Path assumption:** the Git Bash launchers hard-code `C:\Program Files\Git\bin\bash.exe`. If Git is installed elsewhere, edit that path in the script.
