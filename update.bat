@echo off
REM AutoBlog update (double-click BEFORE starting the app).
REM Downloads the latest fixes from GitHub.
cd /d "%~dp0"
git pull
echo.
echo Done. Press any key to close.
pause >nul
