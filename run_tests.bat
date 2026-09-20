@echo off
echo ====================================================
echo Running Fallow Backend Automated Test Suite (T1-T8)...
echo ====================================================
cd /d "%~dp0"
python -m pytest backend/tests/ -v
pause
