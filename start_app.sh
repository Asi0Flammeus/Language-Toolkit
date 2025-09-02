#!/bin/bash

# Pull latest changes from git
echo "Pulling latest changes from git..."
git pull

# Detect and activate virtual environment
echo "Detecting virtual environment..."
if [ -d "venv" ]; then
    echo "Found 'venv' directory"
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        echo "Activating virtual environment (Windows)..."
        source venv/Scripts/activate 2>/dev/null || venv\\Scripts\\activate.bat
    else
        # Linux/Mac
        echo "Activating virtual environment (Linux/Mac)..."
        source venv/bin/activate
    fi
elif [ -d "env" ]; then
    echo "Found 'env' directory"
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        # Windows
        echo "Activating virtual environment (Windows)..."
        source env/Scripts/activate 2>/dev/null || env\\Scripts\\activate.bat
    else
        # Linux/Mac
        echo "Activating virtual environment (Linux/Mac)..."
        source env/bin/activate
    fi
else
    echo "Error: No virtual environment found (looked for 'venv' and 'env')"
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    exit 1
fi


# Run the main application
echo "Starting application..."
python main.py
