@echo off

echo Pulling latest changes from git...
git pull

echo Detecting virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo Found 'venv' directory
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    echo Found 'env' directory
    echo Activating virtual environment...
    call env\Scripts\activate.bat
) else (
    echo Error: No virtual environment found ^(looked for 'venv' and 'env'^)
    echo Please create a virtual environment first:
    echo   python -m venv venv
    pause
    exit /b 1
)

echo Starting application...
python main.py

pause
