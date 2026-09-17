@echo off
REM AutoBlog 로컬 실행 (더블클릭)
REM 최초 1회: pip install -r requirements.txt
cd /d "%~dp0"
streamlit run app.py --server.port 8501
pause
