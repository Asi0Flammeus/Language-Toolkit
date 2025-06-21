#!/usr/bin/env python3
"""
Simple test script to verify API authentication is working
"""
import requests
import json
import sys

# Test configuration
API_BASE_URL = "http://localhost:8000"
VALID_TOKEN = "token_admin_abc123def456"  # From auth_tokens.json
INVALID_TOKEN = "invalid_token_123"

def test_health_endpoint():
    """Test the health endpoint (no auth required)"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Health endpoint working")
            return True
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Health endpoint error: {e}")
        return False

def test_root_endpoint():
    """Test the root endpoint (no auth required)"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print("✓ Root endpoint working")
            return True
        else:
            print(f"✗ Root endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Root endpoint error: {e}")
        return False

def test_authenticated_endpoint_without_token():
    """Test an authenticated endpoint without token (should fail)"""
    try:
        response = requests.get(f"{API_BASE_URL}/tasks")
        if response.status_code == 401:
            print("✓ Authentication required correctly (no token)")
            return True
        else:
            print(f"✗ Expected 401, got: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Test error: {e}")
        return False

def test_authenticated_endpoint_with_invalid_token():
    """Test an authenticated endpoint with invalid token (should fail)"""
    try:
        headers = {"Authorization": f"Bearer {INVALID_TOKEN}"}
        response = requests.get(f"{API_BASE_URL}/tasks", headers=headers)
        if response.status_code == 401:
            print("✓ Invalid token rejected correctly")
            return True
        else:
            print(f"✗ Expected 401, got: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Test error: {e}")
        return False

def test_authenticated_endpoint_with_valid_token():
    """Test an authenticated endpoint with valid token (should succeed)"""
    try:
        headers = {"Authorization": f"Bearer {VALID_TOKEN}"}
        response = requests.get(f"{API_BASE_URL}/tasks", headers=headers)
        if response.status_code == 200:
            print("✓ Valid token accepted correctly")
            return True
        else:
            print(f"✗ Expected 200, got: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Test error: {e}")
        return False

def main():
    """Run all authentication tests"""
    print("Testing API Server Authentication...")
    print("=" * 50)
    
    tests = [
        test_health_endpoint,
        test_root_endpoint,
        test_authenticated_endpoint_without_token,
        test_authenticated_endpoint_with_invalid_token,
        test_authenticated_endpoint_with_valid_token
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All authentication tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())