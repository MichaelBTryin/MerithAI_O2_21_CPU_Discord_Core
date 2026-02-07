@echo off
REM Merith AI Bot - Launch Script
REM This script activates the virtual environment and runs the bot

echo.
echo ============================================================
echo Merith AI Discord Voice Bot
echo CPU-Optimized for Surface Pro 5
echo ============================================================
echo.

REM Check if venv exists
if not exist "venv" (
    echo ERROR: Virtual environment not found
    echo.
    echo Please run install.bat first to set up everything
    echo.
    pause
    exit /b 1
)

REM Check if bot.py exists
if not exist "bot.py" (
    echo ERROR: bot.py not found
    echo Make sure you're in the Example_Simple_Bot folder
    echo.
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found
    echo.
    echo Please run install.bat first to create your .env file
    echo.
    pause
    exit /b 1
)

REM Check if LM Studio is running
echo Checking if LM Studio is running...
echo.

setlocal enabledelayedexpansion
set "max_attempts=10"
set "attempt=0"

:check_lm_studio
set /a attempt=!attempt!+1
echo Checking LM Studio... (attempt !attempt!/!max_attempts!)

REM Try to call LM Studio API using curl
curl -s http://localhost:1234/v1/models >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ✓ LM Studio is ready!
    echo.
    goto lm_studio_ready
)

if !attempt! geq !max_attempts! (
    echo.
    echo ERROR: Cannot connect to LM Studio
    echo.
    echo Troubleshooting:
    echo - Make sure LM Studio is running and listening on port 1234
    echo - Check that your model is loaded in LM Studio
    echo - Restart LM Studio and try again
    echo.
    pause
    exit /b 1
)

timeout /t 1 /nobreak
goto check_lm_studio

:lm_studio_ready

REM Activate venv and run bot
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo ============================================================
echo Starting bot...
echo ============================================================
echo.
echo LM Studio is running on port 1234
echo.
echo Press Ctrl+C to stop the bot
echo.

python bot.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERROR: Bot crashed!
    echo ============================================================
    echo.
    echo Common issues:
    echo - LM Studio not running or model not loaded
    echo - Discord token invalid (check .env file)
    echo - Network/firewall blocking port 1234
    echo - Python dependencies not installed (run install.bat)
    echo.
    pause
    exit /b 1
)
