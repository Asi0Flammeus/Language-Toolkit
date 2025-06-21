#!/bin/bash

# Language Toolkit API Test Script
# This script helps you test the API endpoints using curl commands

API_BASE="http://localhost:8000"
TEST_FILES_DIR="./test-app"

echo "🧪 Language Toolkit API Test Suite"
echo "=================================="

# Check if API is running
echo "📡 Checking API health..."
if curl -s "$API_BASE/health" > /dev/null; then
    echo "✅ API is running and healthy"
else
    echo "❌ API is not accessible. Please start the API server first:"
    echo "   python api_server.py"
    exit 1
fi

echo ""
echo "🔍 Available test files:"
find "$TEST_FILES_DIR" -type f -name "*.pptx" -o -name "*.txt" -o -name "*.mp3" | head -10

echo ""
echo "📋 Available API endpoints:"
curl -s "$API_BASE/" | jq '.endpoints' 2>/dev/null || echo "Install jq for better JSON formatting"

echo ""
echo "🚀 Quick Test Commands:"
echo ""

echo "1️⃣  Test PPTX Translation (EN -> FR):"
echo "curl -X POST \"$API_BASE/translate/pptx\" \\"
echo "  -F \"source_lang=en\" \\"
echo "  -F \"target_lang=fr\" \\"
echo "  -F \"files=@$TEST_FILES_DIR/ECO102-FR-V001-2.1.pptx\""
echo ""

echo "2️⃣  Test Text Translation (EN -> FR):"
echo "curl -X POST \"$API_BASE/translate/text\" \\"
echo "  -F \"source_lang=en\" \\"
echo "  -F \"target_lang=fr\" \\"
echo "  -F \"files=@$TEST_FILES_DIR/btc204/00.txt\""
echo ""

echo "3️⃣  Test Audio Transcription:"
echo "curl -X POST \"$API_BASE/transcribe/audio\" \\"
echo "  -F \"files=@$TEST_FILES_DIR/btc204/00.mp3\""
echo ""

echo "4️⃣  Test PPTX to PDF Conversion:"
echo "curl -X POST \"$API_BASE/convert/pptx\" \\"
echo "  -F \"output_format=pdf\" \\"
echo "  -F \"files=@$TEST_FILES_DIR/ECO102-FR-V001-2.1.pptx\""
echo ""

echo "5️⃣  Test Text-to-Speech:"
echo "curl -X POST \"$API_BASE/tts\" \\"
echo "  -F \"files=@$TEST_FILES_DIR/test_Loic.txt\""
echo ""

echo "6️⃣  Check task status (replace TASK_ID):"
echo "curl \"$API_BASE/tasks/TASK_ID\""
echo ""

echo "7️⃣  Download results (replace TASK_ID):"
echo "curl -O \"$API_BASE/download/TASK_ID\""
echo ""

echo "8️⃣  List all tasks:"
echo "curl \"$API_BASE/tasks\""
echo ""

echo "9️⃣  Cleanup task (replace TASK_ID):"
echo "curl -X DELETE \"$API_BASE/tasks/TASK_ID\""
echo ""

# Interactive mode
echo "🔧 Interactive Testing Mode"
echo "=========================="
echo ""
read -p "Do you want to run an interactive test? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Select a test to run:"
    echo "1) PPTX Translation"
    echo "2) Text Translation" 
    echo "3) Audio Transcription"
    echo "4) PPTX Conversion"
    echo "5) List all tasks"
    echo ""
    read -p "Enter your choice (1-5): " choice
    
    case $choice in
        1)
            echo "🔄 Testing PPTX Translation..."
            RESPONSE=$(curl -s -X POST "$API_BASE/translate/pptx" \
                -F "source_lang=en" \
                -F "target_lang=fr" \
                -F "files=@$TEST_FILES_DIR/ECO102-FR-V001-2.1.pptx")
            echo "Response: $RESPONSE"
            
            # Extract task ID and check status
            TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id' 2>/dev/null)
            if [ "$TASK_ID" != "null" ] && [ "$TASK_ID" != "" ]; then
                echo "✅ Task created with ID: $TASK_ID"
                echo "⏳ Checking task status..."
                sleep 2
                curl -s "$API_BASE/tasks/$TASK_ID" | jq '.' 2>/dev/null || echo "Task status check completed"
            fi
            ;;
        2)
            echo "🔄 Testing Text Translation..."
            RESPONSE=$(curl -s -X POST "$API_BASE/translate/text" \
                -F "source_lang=en" \
                -F "target_lang=fr" \
                -F "files=@$TEST_FILES_DIR/btc204/00.txt")
            echo "Response: $RESPONSE"
            ;;
        3)
            echo "🔄 Testing Audio Transcription..."
            RESPONSE=$(curl -s -X POST "$API_BASE/transcribe/audio" \
                -F "files=@$TEST_FILES_DIR/btc204/00.mp3")
            echo "Response: $RESPONSE"
            ;;
        4)
            echo "🔄 Testing PPTX Conversion..."
            RESPONSE=$(curl -s -X POST "$API_BASE/convert/pptx" \
                -F "output_format=pdf" \
                -F "files=@$TEST_FILES_DIR/ECO102-FR-V001-2.1.pptx")
            echo "Response: $RESPONSE"
            ;;
        5)
            echo "📋 Listing all tasks..."
            curl -s "$API_BASE/tasks" | jq '.' 2>/dev/null || curl -s "$API_BASE/tasks"
            ;;
        *)
            echo "Invalid choice"
            ;;
    esac
fi

echo ""
echo "📚 For more comprehensive testing, use the React app:"
echo "   cd api-test-app"
echo "   npm install"
echo "   npm start"
echo ""
echo "🌐 Or visit the interactive API docs:"
echo "   http://localhost:8000/docs"