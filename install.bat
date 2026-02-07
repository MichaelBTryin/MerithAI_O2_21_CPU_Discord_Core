@echo off
REM Merith AI Bot - Installation Script
REM Installs: Python, Ollama, creates venv, installs Python dependencies, sets up Discord token

echo.
echo ============================================================
echo Merith AI Discord Voice Bot - Installation
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.9+ from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    exit /b 1
)

echo [1/8] Python found:
python --version
echo.

REM Get Discord token (only if .env doesn't exist)
if not exist ".env" (
    echo [2/8] Setting up Discord token...
    echo.
    echo To get your Discord token:
    echo   1. Go to: https://discord.com/developers/applications
    echo   2. Click "New Application" or select existing one
    echo   3. Go to "Bot" tab
    echo   4. Click "Copy" under TOKEN
    echo.
    set /p token="Paste your Discord token here: "

    if "%token%"=="" (
        echo.
        echo ERROR: No token entered!
        echo Token is REQUIRED to run the bot.
        echo Please run install.bat again and provide your token.
        echo.
        pause
        exit /b 1
    )

    REM Create .env file
    (
        echo # Discord Bot Token
        echo DISCORD_TOKEN=%token%
    ) > .env

    echo .env file created successfully!
    echo.
) else (
    echo [2/8] .env file already exists
    echo Skipping token setup...
    echo.
)

REM Create model directories using %userprofile%
echo [3/6] Setting up model directories...
echo.
set piper_dir=%userprofile%\.local\share\piper\models
set whisper_dir=%userprofile%\.cache\huggingface\hub
mkdir "%piper_dir%" >nul 2>&1
mkdir "%whisper_dir%" >nul 2>&1
echo Model directories configured:
echo   Piper:  %piper_dir%
echo   Whisper: %whisper_dir%
echo.

REM Check for FFmpeg
echo [4/8] Checking FFmpeg installation...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo FFmpeg not found. Installing...
    echo.
    REM Try winget first (Windows 10/11)
    winget install FFmpeg -e --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        REM Fallback to chocolatey
        choco install ffmpeg -y >nul 2>&1
        if errorlevel 1 (
            echo WARNING: Could not auto-install FFmpeg (continuing anyway)
        ) else (
            echo ✓ FFmpeg installed via Chocolatey
            echo.
        )
    ) else (
        echo ✓ FFmpeg installed via winget
        echo.
    )
) else (
    echo ✓ FFmpeg already installed
    echo.
)

REM Check for LM Studio (check multiple common install paths)
echo [5/8] Checking LM Studio installation...
if exist "%ProgramFiles%\LM Studio" (
    echo ✓ LM Studio already installed
    echo.
) else if exist "%ProgramFiles(x86)%\LM Studio" (
    echo ✓ LM Studio already installed
    echo.
) else if exist "%LocalAppData%\Programs\LM Studio" (
    echo ✓ LM Studio already installed
    echo.
) else (
    echo LM Studio not found. Installing...
    echo.
    REM Try winget first
    winget install LMStudio -e --accept-source-agreements >nul 2>&1
    if errorlevel 1 (
        REM Fallback to chocolatey
        choco install lmstudio -y >nul 2>&1
        if errorlevel 1 (
            echo WARNING: Could not auto-install LM Studio
            echo Please install manually from: https://lmstudio.ai
        ) else (
            echo ✓ LM Studio installed via Chocolatey
            echo.
        )
    ) else (
        echo ✓ LM Studio installed via winget
        echo.
    )
)

REM Guide user to download model
echo [5b/8] LM Studio Model Download Guide
echo.
echo NEXT STEPS (required before running bot):
echo.
echo 1. Open LM Studio application
echo 2. Click "Search models" on the left sidebar
echo 3. Search for: "gemma-3-1b-it-abliterated"
echo 4. Find: "mlabonne/gemma-3-1b-it-abliterated-GGUF"
echo 5. Click the download button (Q4_K_M variant recommended)
echo 6. Wait for download to complete
echo 7. Click "Load model" when download finishes
echo 8. LM Studio will start the server on port 1234
echo.
echo THEN run: run.bat
echo.
pause

REM Check if venv already exists
if exist "venv" (
    echo [6/8] Virtual environment already exists at .\venv
    echo Skipping venv creation...
    echo.
) else (
    echo [6/8] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created successfully!
    echo.
)

REM Activate venv
echo [7/8] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    exit /b 1
)
echo Virtual environment activated!
echo.

REM Install requirements
echo [7/8] Installing Python dependencies...
echo This may take 5-10 minutes on first run...
echo.
echo Running: pip install -r requirements.txt
echo.
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

echo.
echo ============================================================
echo [8/8] SUCCESS! Installation complete!
echo ============================================================
echo.
echo Model directories created:
echo   Piper voices:  %userprofile%\.local\share\piper\models
echo   Whisper cache: %userprofile%\.cache\huggingface\hub
echo.
echo Prerequisites:
echo   1. Install LM Studio from https://lmstudio.ai
echo   2. Load model: mlabonne/gemma-3-1b-it-abliterated-GGUF (Q4_K_M)
echo   3. Start LM Studio (let it run in background)
echo.
echo Your Discord token is saved in: .env
echo.
echo Next step: Run the bot!
echo.
echo   Double-click: run.bat
echo.
echo   This will:
echo   - Check LM Studio is running
echo   - Connect bot to LM Studio
echo   - Bot comes online in Discord
echo.
echo In Discord:
echo   - Type: @bot_name hello
echo   - Bot responds with text
echo   - Use /join to connect to voice channel
echo.
echo For more help, see: README.md
echo.
