#!/usr/bin/env python3
"""
Test script for transcript cleaning feature.

This script tests the transcript cleaning functionality with a sample transcript.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import core modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.transcript_cleaner import TranscriptCleanerCore
from core.config import ConfigManager

def test_transcript_cleaning():
    """Test transcript cleaning with a sample transcript."""
    
    # Sample raw transcript with filler words and issues
    sample_transcript = """
    So, um, today I'm going to, uh, talk about, you know, the importance of clean code.
    So like, when we write code, it's really really important that we, um, make it readable.
    
    Uh, one thing that's super important is, you know, is that we need to like follow
    conventions and and and make sure our code is, uh, maintainable. You know what I mean?
    
    So basically, um, there are three main principles we should follow:
    First, uh, we need to write self-documenting code. Like, the code should should explain itself.
    Second, um, we should avoid, you know, complex nested structures that are like hard to follow.
    And third, uh, we need to, um, consistently apply our coding standards across the the whole project.
    
    So yeah, that's basically what I wanted to, uh, share about clean code today. Um, any questions?
    """
    
    print("=" * 60)
    print("TRANSCRIPT CLEANER TEST")
    print("=" * 60)
    print("\nOriginal transcript:")
    print("-" * 40)
    print(sample_transcript)
    print("-" * 40)
    
    # Get API key from config
    config = ConfigManager()
    api_keys = config.get_api_keys()
    anthropic_key = api_keys.get('anthropic')
    
    if not anthropic_key:
        print("\n❌ ERROR: Anthropic API key not configured.")
        print("Please configure your API key in the application settings.")
        return False
    
    # Initialize the cleaner
    print("\n🔄 Initializing transcript cleaner...")
    
    def progress_callback(msg):
        print(f"  ➜ {msg}")
    
    try:
        cleaner = TranscriptCleanerCore(
            api_key=anthropic_key,
            progress_callback=progress_callback
        )
        
        print("\n🤖 Cleaning transcript with Claude AI...")
        cleaned_transcript = cleaner.clean_transcript_text(sample_transcript)
        
        print("\n✅ Cleaned transcript:")
        print("-" * 40)
        print(cleaned_transcript)
        print("-" * 40)
        
        # Calculate statistics
        original_words = len(sample_transcript.split())
        cleaned_words = len(cleaned_transcript.split())
        reduction = ((original_words - cleaned_words) / original_words) * 100
        
        print(f"\n📊 Statistics:")
        print(f"  • Original word count: {original_words}")
        print(f"  • Cleaned word count: {cleaned_words}")
        print(f"  • Reduction: {reduction:.1f}%")
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

def test_file_processing():
    """Test processing a transcript file."""
    
    print("\n" + "=" * 60)
    print("FILE PROCESSING TEST")
    print("=" * 60)
    
    # Create a test file
    test_dir = Path("tests/temp")
    test_dir.mkdir(exist_ok=True)
    
    test_file = test_dir / "test_transcript.txt"
    test_file.write_text("""
    Um, so this is a test transcript that, uh, needs cleaning.
    You know, it has lots of, like, filler words and stuff.
    We should should remove the repetitions and, um, make it cleaner.
    """)
    
    print(f"\n📁 Created test file: {test_file}")
    
    # Get API key
    config = ConfigManager()
    api_keys = config.get_api_keys()
    anthropic_key = api_keys.get('anthropic')
    
    if not anthropic_key:
        print("\n❌ ERROR: Anthropic API key not configured.")
        return False
    
    def progress_callback(msg):
        print(f"  ➜ {msg}")
    
    try:
        cleaner = TranscriptCleanerCore(
            api_key=anthropic_key,
            progress_callback=progress_callback
        )
        
        print("\n🔄 Processing file...")
        success = cleaner.clean_transcript_file(test_file)
        
        if success:
            cleaned_file = test_file.parent / f"{test_file.stem}-ai-cleaned.txt"
            if cleaned_file.exists():
                print(f"\n✅ Cleaned file created: {cleaned_file}")
                print("\nCleaned content:")
                print("-" * 40)
                print(cleaned_file.read_text())
                print("-" * 40)
                
                # Clean up
                test_file.unlink()
                cleaned_file.unlink()
                print("\n🧹 Test files cleaned up")
                
                return True
            else:
                print("\n❌ ERROR: Cleaned file was not created")
                return False
        else:
            print("\n❌ ERROR: File processing failed")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        # Clean up on error
        if test_file.exists():
            test_file.unlink()
        return False

if __name__ == "__main__":
    print("\n🚀 Starting Transcript Cleaner Tests\n")
    
    # Run tests
    test1_passed = test_transcript_cleaning()
    test2_passed = test_file_processing()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  • Text cleaning test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"  • File processing test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")
        sys.exit(1)