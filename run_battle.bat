@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" battle_demo.py
) else (
  python battle_demo.py
)
if errorlevel 1 pause
