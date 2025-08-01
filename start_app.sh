#!/bin/bash

# Pull latest changes from git
echo "Pulling latest changes from git..."
git pull

# Activate virtual environment
if [ -d "env" ]; then
    echo "Activating virtual environment..."
    source env/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "No virtual environment found. Please create one first."
    exit 1
fi

# Update requirements
echo "Updating requirements..."
pip install -r requirements.txt

# Start the application
echo "Starting the application..."
python main.py