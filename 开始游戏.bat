@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DANGLING
python -c "import pygame" 2>nul
if errorlevel 1 (
    echo [!] pygame not found. Installing pygame-ce ...
    python -m pip install pygame-ce
    if errorlevel 1 (
        echo [!] Install failed. Run:  pip install pygame-ce
        pause
        exit /b 1
    )
)
python run.py
if errorlevel 1 pause
