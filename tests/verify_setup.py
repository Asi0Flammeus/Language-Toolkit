#!/usr/bin/env python3
"""
Verify that the Clean Raw Transcript feature is properly set up.
"""

import sys
from pathlib import Path
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def verify_setup():
    """Verify all components are properly configured."""
    print("🔍 Verifying Clean Raw Transcript Feature Setup\n")
    
    checks_passed = []
    checks_failed = []
    
    # 1. Check module import
    print("1. Checking module imports...")
    try:
        from core.transcript_cleaner import TranscriptCleanerCore
        print("   ✅ TranscriptCleanerCore module imported successfully")
        checks_passed.append("Module import")
    except ImportError as e:
        print(f"   ❌ Failed to import module: {e}")
        checks_failed.append("Module import")
    
    # 2. Check API key configuration
    print("\n2. Checking API key configuration...")
    from core.config import ConfigManager
    config = ConfigManager()
    api_keys = config.get_api_keys()
    
    if "anthropic" in api_keys and api_keys["anthropic"]:
        print(f"   ✅ Anthropic API key is configured (from {'environment' if os.getenv('ANTHROPIC_API_KEY') else 'config file'})")
        checks_passed.append("API key configuration")
    else:
        print("   ⚠️  Anthropic API key not configured")
        print("      Configure via: Configuration → API Keys menu or ANTHROPIC_API_KEY environment variable")
        checks_failed.append("API key configuration")
    
    # 3. Check GUI integration
    print("\n3. Checking GUI integration...")
    try:
        # Check if TranscriptCleanerTool is defined in main.py
        with open("main.py", "r") as f:
            main_content = f.read()
        
        if "class TranscriptCleanerTool(ToolBase):" in main_content:
            print("   ✅ TranscriptCleanerTool class defined in main.py")
            checks_passed.append("GUI tool class")
        else:
            print("   ❌ TranscriptCleanerTool class not found in main.py")
            checks_failed.append("GUI tool class")
        
        if '"Clean Transcript"' in main_content:
            print("   ✅ Clean Transcript tab added to GUI")
            checks_passed.append("GUI tab")
        else:
            print("   ❌ Clean Transcript tab not found in GUI")
            checks_failed.append("GUI tab")
            
    except Exception as e:
        print(f"   ❌ Error checking GUI integration: {e}")
        checks_failed.append("GUI integration")
    
    # 4. Check API endpoints
    print("\n4. Checking API endpoints...")
    try:
        with open("api_server.py", "r") as f:
            api_content = f.read()
        
        if '@app.post("/clean/transcript"' in api_content:
            print("   ✅ /clean/transcript endpoint defined")
            checks_passed.append("API endpoint")
        else:
            print("   ❌ /clean/transcript endpoint not found")
            checks_failed.append("API endpoint")
            
        if '@app.post("/clean/transcript_s3"' in api_content:
            print("   ✅ /clean/transcript_s3 endpoint defined")
            checks_passed.append("S3 API endpoint")
        else:
            print("   ❌ /clean/transcript_s3 endpoint not found")
            checks_failed.append("S3 API endpoint")
            
    except Exception as e:
        print(f"   ❌ Error checking API endpoints: {e}")
        checks_failed.append("API endpoints")
    
    # 5. Check tool descriptions
    print("\n5. Checking tool descriptions...")
    try:
        from core.tool_descriptions import get_tool_requirements, get_tool_descriptions
        
        requirements = get_tool_requirements()
        descriptions = get_tool_descriptions()
        
        if "transcript_cleaner" in requirements:
            req = requirements["transcript_cleaner"]
            print(f"   ✅ Tool requirements defined: {req['api_required']}")
            checks_passed.append("Tool requirements")
        else:
            print("   ❌ Tool requirements not defined")
            checks_failed.append("Tool requirements")
            
        if "transcript_cleaner" in descriptions:
            print(f"   ✅ Tool description defined: {descriptions['transcript_cleaner']['title']}")
            checks_passed.append("Tool description")
        else:
            print("   ❌ Tool description not defined")
            checks_failed.append("Tool description")
            
    except Exception as e:
        print(f"   ❌ Error checking tool descriptions: {e}")
        checks_failed.append("Tool descriptions")
    
    # 6. Check sample files
    print("\n6. Checking sample files...")
    sample_file = Path("examples/sample_raw_transcript.txt")
    if sample_file.exists():
        print(f"   ✅ Sample transcript file exists: {sample_file}")
        checks_passed.append("Sample file")
    else:
        print("   ⚠️  Sample transcript file not found")
        checks_failed.append("Sample file")
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {len(checks_passed)} checks")
    print(f"❌ Failed: {len(checks_failed)} checks")
    
    if checks_failed:
        print("\nFailed checks:")
        for check in checks_failed:
            print(f"  • {check}")
    
    if len(checks_failed) == 0:
        print("\n🎉 All checks passed! Clean Raw Transcript feature is fully configured.")
        return True
    elif len(checks_failed) == 1 and "API key configuration" in checks_failed:
        print("\n✅ Setup complete! Just need to configure the Anthropic API key to use the feature.")
        return True
    else:
        print("\n⚠️  Some components need attention. Please review the failed checks above.")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("CLEAN RAW TRANSCRIPT FEATURE VERIFICATION")
    print("=" * 60)
    print()
    
    success = verify_setup()
    
    sys.exit(0 if success else 1)