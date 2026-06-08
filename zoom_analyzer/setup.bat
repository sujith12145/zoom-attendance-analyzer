@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM setup.bat  -  One-command setup for Zoom Attendance Analyzer (Windows)
REM Usage: Double-click or run from Command Prompt
REM ──────────────────────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║     Zoom Attendance Analyzer - Setup (Windows)       ║
echo ╚══════════════════════════════════════════════════════╝
echo.

REM Check Python
python --version
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo.
echo Generating sample data...
python generate_sample_data.py

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  Setup complete!                                     ║
echo ║                                                      ║
echo ║  To start:  streamlit run app.py                     ║
echo ║  Open:      http://localhost:8501                    ║
echo ╚══════════════════════════════════════════════════════╝
echo.
pause
