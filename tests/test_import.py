#!/usr/bin/env python3
"""
Test that the transcript cleaner module can be imported successfully.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    
    try:
        from core.transcript_cleaner import TranscriptCleanerCore
        print("✅ TranscriptCleanerCore imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TranscriptCleanerCore: {e}")
        return False
    
    try:
        from core.config import ConfigManager
        print("✅ ConfigManager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ConfigManager: {e}")
        return False
    
    try:
        import anthropic
        print("✅ anthropic package imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import anthropic package: {e}")
        return False
    
    return True

def test_class_instantiation():
    """Test that the class can be instantiated with a dummy key."""
    print("\nTesting class instantiation...")
    
    try:
        from core.transcript_cleaner import TranscriptCleanerCore
        
        # Try to create instance with dummy key (won't work for API calls but tests init)
        cleaner = TranscriptCleanerCore(
            api_key="dummy-key-for-testing",
            progress_callback=lambda x: None
        )
        print("✅ TranscriptCleanerCore instantiated successfully")
        
        # Check that methods exist
        assert hasattr(cleaner, 'clean_transcript_text')
        assert hasattr(cleaner, 'clean_transcript_file')
        assert hasattr(cleaner, 'clean_folder')
        print("✅ All expected methods are present")
        
        return True
    except Exception as e:
        print(f"❌ Failed to instantiate TranscriptCleanerCore: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TRANSCRIPT CLEANER MODULE TEST")
    print("=" * 60)
    print()
    
    test1 = test_imports()
    test2 = test_class_instantiation()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  • Import test: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"  • Instantiation test: {'✅ PASSED' if test2 else '❌ FAILED'}")
    
    if test1 and test2:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed.")
        sys.exit(1)