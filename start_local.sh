#!/bin/bash
# Quick start script for Language Toolkit local deployment

echo "🚀 Language Toolkit Local Deployment Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}❌ npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites installed${NC}"

# Check if we're in the right directory
if [ ! -f "api_server.py" ]; then
    echo -e "${RED}❌ Error: api_server.py not found. Please run this script from the language_toolkit directory${NC}"
    exit 1
fi

# Setup Python environment
echo -e "\n${YELLOW}Setting up Python environment...${NC}"

if [ ! -d "env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv env
fi

# Activate virtual environment
source env/bin/activate

# Install/upgrade pip
pip install --upgrade pip >/dev/null 2>&1

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing API dependencies..."
    if [ -f "api_requirements.txt" ]; then
        pip install -r api_requirements.txt
    else
        pip install fastapi uvicorn python-dotenv boto3 python-jose[cryptography] \
                    python-multipart aiofiles requests deepl openai elevenlabs \
                    convertapi pydub moviepy
    fi
fi

# Check configuration files
echo -e "\n${YELLOW}Checking configuration files...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        cat > .env << EOL
# API Keys - Please fill in your actual keys
DEEPL_API_KEY=your_deepl_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
CONVERTAPI_SECRET=your_convertapi_secret_here

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
EOL
    fi
    echo -e "${RED}❗ Please edit .env file with your API keys${NC}"
fi

# Note: api_keys.json is deprecated - all API keys should now be in .env file
if [ -f "api_keys.json" ]; then
    echo -e "${YELLOW}ℹ️  Note: api_keys.json is deprecated. API keys should be in .env file${NC}"
fi

if [ ! -f "auth_tokens.json" ]; then
    echo -e "${YELLOW}⚠️  auth_tokens.json not found. Creating default...${NC}"
    if [ -f "auth_tokens.json.example" ]; then
        cp auth_tokens.json.example auth_tokens.json
    else
        cat > auth_tokens.json << EOL
{
  "tokens": {
    "token_admin_abc123def456": {
      "name": "Admin User",
      "role": "admin",
      "created": "2024-01-01"
    }
  }
}
EOL
    fi
fi

# Check if ports are available
echo -e "\n${YELLOW}Checking port availability...${NC}"

if port_in_use 8000; then
    echo -e "${RED}❌ Port 8000 is already in use${NC}"
    echo "Please stop the existing service or use a different port"
    exit 1
fi

if port_in_use 3000; then
    echo -e "${YELLOW}⚠️  Port 3000 is already in use (probably another React app)${NC}"
    echo "The test app will use the next available port"
fi

# Function to start API server
start_api_server() {
    echo -e "\n${GREEN}Starting API Server on http://localhost:8000${NC}"
    echo "API Docs will be available at http://localhost:8000/docs"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    python api_server.py
}

# Function to start test app
start_test_app() {
    cd api-test-app
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo -e "\n${YELLOW}Installing test app dependencies...${NC}"
        npm install
    fi
    
    # Use enhanced app if available
    if [ -f "src/App.enhanced.js" ]; then
        echo -e "\n${GREEN}Using enhanced test app${NC}"
        cp src/App.enhanced.js src/App.js
    fi
    
    echo -e "\n${GREEN}Starting Test App on http://localhost:3000${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    npm start
}

# Menu
echo -e "\n${YELLOW}What would you like to start?${NC}"
echo "1) API Server only"
echo "2) Test App only"
echo "3) Both (in separate terminals)"
echo "4) Exit"

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        start_api_server
        ;;
    2)
        start_test_app
        ;;
    3)
        echo -e "\n${YELLOW}Starting both services...${NC}"
        echo "Opening new terminal for API server..."
        
        # Try different terminal emulators
        if command_exists gnome-terminal; then
            gnome-terminal -- bash -c "cd '$PWD' && source env/bin/activate && python api_server.py; exec bash"
        elif command_exists xterm; then
            xterm -e "cd '$PWD' && source env/bin/activate && python api_server.py; bash" &
        elif command_exists konsole; then
            konsole -e bash -c "cd '$PWD' && source env/bin/activate && python api_server.py; exec bash" &
        else
            echo -e "${YELLOW}Could not open new terminal. Please manually run in a new terminal:${NC}"
            echo "cd $PWD"
            echo "source env/bin/activate"
            echo "python api_server.py"
        fi
        
        # Give API server time to start
        echo "Waiting for API server to start..."
        sleep 3
        
        # Start test app in current terminal
        start_test_app
        ;;
    4)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac