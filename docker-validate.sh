#!/bin/bash

# Docker Configuration Validation Script
# Validates all required files and configurations before deployment

set -e

echo "🔍 Language Toolkit API Configuration Validation"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation results
VALIDATION_PASSED=true

# Function to check file existence
check_file() {
    local file=$1
    local required=$2
    local example_file="${file}.example"
    
    if [ -f "$file" ]; then
        echo -e "✅ ${GREEN}$file${NC} exists"
        return 0
    elif [ -f "$example_file" ] && [ "$required" = "optional" ]; then
        echo -e "⚠️  ${YELLOW}$file${NC} missing but ${example_file} available"
        return 0
    else
        echo -e "❌ ${RED}$file${NC} missing"
        if [ "$required" = "required" ]; then
            VALIDATION_PASSED=false
        fi
        return 1
    fi
}

# Function to check directory
check_directory() {
    local dir=$1
    if [ -d "$dir" ]; then
        echo -e "✅ ${GREEN}Directory $dir${NC} exists"
        return 0
    else
        echo -e "❌ ${RED}Directory $dir${NC} missing"
        VALIDATION_PASSED=false
        return 1
    fi
}

# Function to validate JSON file
validate_json() {
    local file=$1
    if [ -f "$file" ]; then
        if python3 -m json.tool "$file" > /dev/null 2>&1; then
            echo -e "✅ ${GREEN}$file${NC} is valid JSON"
            return 0
        else
            echo -e "❌ ${RED}$file${NC} contains invalid JSON"
            VALIDATION_PASSED=false
            return 1
        fi
    fi
}

echo ""
echo "📋 Checking Required Files..."
echo "-----------------------------"

# Check Docker files
check_file "Dockerfile" "required"
check_file "Dockerfile.prod" "required"  
check_file "docker-compose.yml" "required"

# Check configuration files
check_file "api_keys.json" "optional"
check_file "auth_tokens.json" "optional"
check_file "client_credentials.json" "optional"

# Check docker directory
if check_directory "docker"; then
    check_file "docker/gunicorn.conf.py" "required"
    check_file "docker/entrypoint.sh" "required"
fi

echo ""
echo "📁 Checking Directories..."
echo "--------------------------"

check_directory "logs"
check_directory "temp" 
check_directory "uploads"
check_directory "core"

echo ""
echo "🔧 Validating JSON Configuration..."
echo "----------------------------------"

validate_json "api_keys.json"
validate_json "auth_tokens.json"
validate_json "client_credentials.json"
validate_json "supported_languages.json"

echo ""
echo "🐳 Checking Docker Environment..."
echo "--------------------------------"

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "✅ ${GREEN}Docker${NC} is installed"
    if docker info > /dev/null 2>&1; then
        echo -e "✅ ${GREEN}Docker daemon${NC} is running"
    else
        echo -e "❌ ${RED}Docker daemon${NC} is not running"
        VALIDATION_PASSED=false
    fi
else
    echo -e "❌ ${RED}Docker${NC} is not installed"
    VALIDATION_PASSED=false
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
    echo -e "✅ ${GREEN}Docker Compose${NC} is available"
else
    echo -e "❌ ${RED}Docker Compose${NC} is not installed"
    VALIDATION_PASSED=false
fi

echo ""
echo "🔑 Checking Key Files Content..."
echo "-------------------------------"

# Check if files have actual content (not just examples)
if [ -f "api_keys.json" ]; then
    if grep -q "your_api_key_here\|example\|placeholder" "api_keys.json" 2>/dev/null; then
        echo -e "⚠️  ${YELLOW}api_keys.json${NC} appears to contain placeholder values"
    else
        echo -e "✅ ${GREEN}api_keys.json${NC} appears to have real values"
    fi
fi

if [ -f "client_credentials.json" ]; then
    if grep -q "supersecret123\|example\|placeholder" "client_credentials.json" 2>/dev/null; then
        echo -e "⚠️  ${YELLOW}client_credentials.json${NC} appears to contain example values"
    else
        echo -e "✅ ${GREEN}client_credentials.json${NC} appears to have real values"
    fi
fi

echo ""
echo "🎯 Validation Summary"
echo "==================="

if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "🎉 ${GREEN}All validations passed!${NC}"
    echo ""
    echo "Ready to deploy with:"
    echo "  ./docker-deploy.sh"
    exit 0
else
    echo -e "❌ ${RED}Validation failed!${NC}"
    echo ""
    echo "📋 Required actions:"
    echo "  1. Fix missing files/directories shown above"
    echo "  2. Ensure JSON files are valid"
    echo "  3. Install/start Docker if needed"
    echo "  4. Run validation again: ./docker-validate.sh"
    echo ""
    exit 1
fi