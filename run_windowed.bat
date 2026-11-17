@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" main.py --windowed
) else (
  python main.py --windowed
)
if errorlevel 1 pause
