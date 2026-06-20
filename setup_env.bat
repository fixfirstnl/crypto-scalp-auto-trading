@echo off
echo ============================================
echo  Crypto Scalp Auto Trading - Environment Setup
echo ============================================
echo.

REM Check if .env already exists
if exist .env (
    echo [INFO] .env bestaat al. Wil je het overschrijven?
    choice /C YN /N /M "Overschrijven? (Y/N)"
    if errorlevel 2 goto skip_env
)

REM Copy .env.example to .env
echo [1/3] .env.example kopieren naar .env...
copy .env.example .env >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Kan .env.example niet kopieren!
    echo Zorg dat .env.example in de project folder staat.
    pause
    exit /b 1
)
echo [OK] .env aangemaakt!
echo.

REM Ask user to edit .env
echo [2/3] BELANGRIJK: Bewerk .env nu en vul je API keys in!
echo.
echo   BYBIT_API_KEY=je_api_key
echo   BYBIT_API_SECRET=je_api_secret
echo.

REM Open .env in notepad (if available)
start notepad .env

:skip_env

REM Create data directory
echo [3/3] Data directory aanmaken...
if not exist "data" mkdir data
echo [OK] data/ directory aangemaakt!

REM Create logs directory
if not exist "logs" mkdir logs
echo [OK] logs/ directory aangemaakt!

echo.
echo ============================================
echo  [OK] Setup compleet!
echo ============================================
echo.
echo Volgende stap:
echo   1. Bewerk .env en vul je API keys in
echo   2. Run: python main.py --test-mode
echo.
pause
