@echo off
chcp 65001 >nul
echo ============================================
echo  Crypto Scalp Auto Trading - Setup Script
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is NOT installed!
        echo.
        echo === Installatie instructies ===
        echo 1. Ga naar: https://www.python.org/downloads/release/python-3119/
        echo 2. Download: Windows installer (64-bit)
        echo 3. Installeer met "Add Python to PATH" aangevinkt!
        echo 4. Herstart deze terminal
        echo 5. Run dit script opnieuw: setup.bat
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
) else (
    set PYTHON_CMD=python
)

echo [OK] Python gevonden: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM Check Python version (must be 3.11+)
for /f "tokens=2" %%i in ('%PYTHON_CMD% --version') do set PYVER=%%i
echo Python versie: %PYVER%

REM Upgrade pip
echo [1/4] pip upgraden...
%PYTHON_CMD% -m pip install --upgrade pip

REM Create virtual environment
echo [2/4] Virtual environment aanmaken...
if not exist "venv" (
    %PYTHON_CMD% -m venv venv
    echo [OK] venv aangemaakt
) else (
    echo [OK] venv bestaat al
)

REM Activate venv
echo [3/4] Virtual environment activeren...
call venv\Scripts\activate.bat

REM Install dependencies
echo [4/4] Dependencies installeren...
pip install -r requirements.txt

echo.
echo ============================================
echo  [OK] Setup compleet!
echo ============================================
echo.
echo Volgende stap:
echo   1. Kopieer .env.example naar .env
echo   2. Vul je Bybit Testnet API keys in
echo   3. Run: python main.py
echo.
pause
