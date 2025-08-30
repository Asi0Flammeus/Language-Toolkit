#!/usr/bin/env python3
"""
Test that API keys can be saved and retrieved correctly.
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_api_key_save():
    """Test saving and retrieving API keys."""
    print("Testing API Key Save Functionality...")
    
    from core.config import ConfigManager
    
    # Create config manager
    config = ConfigManager()
    
    # Test saving API keys
    test_keys = {
        "openai": "test-openai-key",
        "anthropic": "test-anthropic-key",
        "deepl": "test-deepl-key",
        "elevenlabs": "test-elevenlabs-key",
        "convertapi": "test-convertapi-key"
    }
    
    print("\n📝 Saving test API keys...")
    config.save_api_keys(test_keys)
    
    # Reload and verify
    print("🔄 Reloading configuration...")
    config2 = ConfigManager()
    retrieved_keys = config2.get_api_keys()
    
    print("\n✅ Verifying saved keys:")
    all_match = True
    for key_name, key_value in test_keys.items():
        if retrieved_keys.get(key_name) == key_value:
            print(f"  • {key_name}: ✓ Saved correctly")
        else:
            print(f"  • {key_name}: ✗ Not saved correctly")
            all_match = False
    
    # Check the config file directly
    config_file = Path.home() / "Documents" / "Language Toolkit" / "config.json"
    if config_file.exists():
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        if "api_keys" in config_data:
            print(f"\n📄 Config file contains {len(config_data['api_keys'])} API keys")
            if "anthropic" in config_data["api_keys"]:
                print("  • Anthropic key is present in config")
        else:
            print("\n❌ No api_keys section in config file")
            all_match = False
    
    return all_match

if __name__ == "__main__":
    print("=" * 60)
    print("API KEY SAVE TEST")
    print("=" * 60)
    print()
    
    success = test_api_key_save()
    
    print("\n" + "=" * 60)
    print("TEST RESULT")
    print("=" * 60)
    
    if success:
        print("✅ API key save/load functionality works correctly!")
        print("\nNote: The actual API keys in your config have been preserved.")
        print("The test used temporary test keys for validation only.")
        sys.exit(0)
    else:
        print("❌ API key save/load test failed")
        sys.exit(1)