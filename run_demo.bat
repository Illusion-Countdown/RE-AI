@echo off
setlocal
cd /d "%~dp0"
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0..\.venv\Scripts\python.exe" set "PY=%~dp0..\.venv\Scripts\python.exe"
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
if not defined PY set "PY=python"
%PY% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 当前 Python 没有 pygame。
    echo 请使用：D:\Pygame\.venv\Scripts\python.exe main.py
    pause
    exit /b 1
)
%PY% main.py
if errorlevel 1 pause
