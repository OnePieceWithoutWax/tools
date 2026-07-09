@echo off
if exist "%CD%\.venv" (
    "C:\Program Files\Git\bin\bash.exe" --login -i -c "cd '%CD:\=/%' && source .venv/Scripts/activate && exec bash"
) else (
    "C:\Program Files\Git\bin\bash.exe" --login -i -c "cd '%CD:\=/%' && exec bash"
)