@echo off
echo ====================================================
echo Starting Fallow FastAPI Backend Server (Port 8000)...
echo ====================================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
