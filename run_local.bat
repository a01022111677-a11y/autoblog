@echo off
REM AutoBlog local start (double-click).
REM This window closes instantly. Server runs hidden, browser opens after boot.
REM First time only: pip install -r requirements.txt
cd /d "%~dp0"
start "" powershell -WindowStyle Hidden -Command "Start-Process streamlit -ArgumentList 'run','app.py','--server.port','8501','--server.headless','true' -WindowStyle Hidden; Start-Sleep -Seconds 7; Start-Process 'http://localhost:8501'"
exit
