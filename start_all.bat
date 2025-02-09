REM filepath: /d:/azalise_ai_git/azalise_ai/start_all.bat
@echo off
title Azalise AI Launcher
echo Starting Azalise AI Services...
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Start the main application in a new window
echo Starting main application...
start cmd /k "python run.py"

REM Change to core directory and start TTS and STT handlers
cd core
echo Starting TTS handler...
start cmd /k "python tts_handler.py"
echo Starting STT handler...
start cmd /k "python stt_handler.py"

REM Wait a moment before closing this window
echo All services started!
timeout /t 3 >nul
exit