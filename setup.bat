@echo off
REM Setup script for ArchiFlow (Windows)

echo Setting up ArchiFlow...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://python.org
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Copy environment template if .env doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env file with your API keys
)

echo.
echo Setup complete! To start using ArchiFlow:
echo   1. Activate the virtual environment: venv\Scripts\activate
echo   2. Edit .env file with your API keys
echo   3. Run: python run_dev.py
echo.
echo For development, install dev dependencies:
echo   pip install -r requirements-dev.txt

pause