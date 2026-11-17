@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" battle_demo.py --windowed
) else (
  python battle_demo.py --windowed
)
if errorlevel 1 pause
