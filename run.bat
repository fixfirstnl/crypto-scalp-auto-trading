@echo off
echo ============================================
echo  Crypto Scalp Auto Trading - Runner
echo  Python 3.12 + CrewAI
echo ============================================
echo.

REM Detect Python 3.12 (preferred) or 3.11
if exist "python_embed312\python.exe" (
    set PYTHON=python_embed312\python.exe
    echo [INFO] Python 3.12 embedded gedetecteerd
) else if exist "python_embed\python.exe" (
    set PYTHON=python_embed\python.exe
    echo [INFO] Python 3.11 embedded gedetecteerd (CrewAI niet beschikbaar)
) else (
    echo [ERROR] Geen Python gevonden!
    echo Zorg dat python_embed312/ of python_embed/ bestaat.
    pause
    exit /b 1
)

REM Show Python version
%PYTHON% --version
echo.

REM Run the trading system with all arguments passed through
%PYTHON% main.py %*

pause
