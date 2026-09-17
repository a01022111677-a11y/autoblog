@echo off
REM AutoBlog local start (double-click). Server runs minimized, browser opens, this window closes.
REM First time only: pip install -r requirements.txt
cd /d "%~dp0"
start "" /min streamlit run app.py --server.port 8501 --server.headless true
timeout /t 6 /nobreak >nul
start "" http://localhost:8501
exit
