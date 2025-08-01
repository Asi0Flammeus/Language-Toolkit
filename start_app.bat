@echo off

echo Pulling latest changes from git...
git pull

echo Activating virtual environment...
if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Please create one first.
    exit /b 1
)

echo Updating requirements...
pip install -q -r requirements.txt

echo Starting the application...
python main.py