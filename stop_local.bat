@echo off
REM AutoBlog server stop (double-click). Kills whatever listens on 8501.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
exit
