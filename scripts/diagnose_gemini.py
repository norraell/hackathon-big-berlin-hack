#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot Gemini API issues.
Run this to identify the root cause of error 1011.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_api_key():
    """Test if API key is configured."""
    print_section("1. API Key Configuration")
    
    try:
        api_key = settings.gemini_api_key
        if not api_key or api_key == "your_gemini_api_key_here":
            print("❌ FAIL: API key not configured")
            print("   Please set GEMINI_API_KEY in your .env file")
            return False
        
        # Mask the key for security
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"✓ API key configured: {masked_key}")
        print(f"  Length: {len(api_key)} characters")
        return True
    except Exception as e:
        print(f"❌ FAIL: Error reading API key: {e}")
        return False


def test_google_genai_import():
    """Test if google-genai package is installed correctly."""
    print_section("2. Package Installation")
    
    try:
        from google import genai
        from google.genai import types
        print("✓ google-genai package installed")
        print(f"  Version: {genai.__version__ if hasattr(genai, '__version__') else 'unknown'}")
        return True, True
            
    except ImportError as e:
        print(f"❌ FAIL: google-genai not installed: {e}")
        print("  Install with: pip install google-genai")
        return False, False


def test_basic_api_access():
    """Test basic API access with new Gemini client."""
    print_section("3. Basic API Access Test")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=settings.gemini_api_key)
        print("✓ Client created successfully")
        
        # Try to list models
        print("\nAttempting to list available models...")
        try:
            models = client.models.list()
            model_names = [m.name for m in models]
            print(f"✓ Successfully retrieved {len(model_names)} models")
            
            print("\nAvailable models:")
            for model in list(models)[:10]:  # Show first 10
                print(f"  - {model.name}")
            
            if len(model_names) > 10:
                print(f"  ... and {len(model_names) - 10} more")
            
            return True, model_names
        except Exception as e:
            print(f"❌ FAIL: Could not list models: {e}")
            print(f"  Error type: {type(e).__name__}")
            
            # Check for common errors
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str:
                print("\n  → This looks like an API key issue")
                print("    - Verify your key at: https://aistudio.google.com/apikey")
                print("    - Make sure it's not expired or revoked")
            elif "quota" in error_str:
                print("\n  → This looks like a quota issue")
                print("    - Check your usage at: https://console.cloud.google.com/")
            elif "permission" in error_str:
                print("\n  → This looks like a permissions issue")
                print("    - Ensure Gemini API is enabled in your project")
            
            return False, []
            
    except Exception as e:
        print(f"❌ FAIL: Error creating client: {e}")
        return False, []


def test_simple_generation():
    """Test simple text generation."""
    print_section("4. Simple Generation Test")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=settings.gemini_api_key)
        
        # Try with gemini-2.5-flash
        print("Testing with gemini-2.5-flash model...")
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents="Say 'Hello' in one word"
            )
            print(f"✓ Generation successful!")
            if response.text:
                print(f"  Response: {response.text[:100]}")
            return True
        except Exception as e:
            print(f"❌ FAIL with gemini-2.5-flash: {e}")
            
            # Try alternative model
            print("\nTrying gemini-pro...")
            try:
                response = client.models.generate_content(
                    model='gemini-pro',
                    contents="Say 'Hello' in one word"
                )
                print(f"✓ Generation successful with gemini-pro!")
                if response.text:
                    print(f"  Response: {response.text[:100]}")
                return True
            except Exception as e2:
                print(f"❌ FAIL with gemini-pro: {e2}")
                return False
                
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


async def test_live_api():
    """Test Gemini Live API access."""
    print_section("5. Live API Test")
    
    try:
        from google import genai
        from google.genai import types
        
        print("✓ New genai client imported successfully")
        
        # Create client
        print("\nCreating Gemini client...")
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            print("✓ Client created successfully")
        except Exception as e:
            print(f"❌ FAIL: Could not create client: {e}")
            return False
        
        # Try to connect to Live API
        print("\nAttempting to connect to Live API...")
        print("  Model: models/gemini-2.0-flash-exp")
        
        # Define config outside try block so it's available in except block
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],  # type: ignore[arg-type]
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            ),
        )
        
        try:
            async with client.aio.live.connect(
                model="models/gemini-2.0-flash-exp",
                config=config
            ) as session:
                print("✓ Successfully connected to Live API!")
                print("  Session established")
                return True
                
        except Exception as e:
            print(f"❌ FAIL: Could not connect to Live API")
            print(f"  Error: {e}")
            print(f"  Error type: {type(e).__name__}")
            
            error_str = str(e)
            if "1011" in error_str:
                print("\n  → Error 1011 detected. Possible causes:")
                print("    1. Live API not available in your region")
                print("    2. Model 'gemini-2.0-flash-exp' not accessible")
                print("    3. Live API not enabled for your account")
                print("    4. API key lacks necessary permissions")
                print("\n  → Recommendations:")
                print("    - Check if you have access to experimental features")
                print("    - Try using a different model")
                print("    - Contact Google Cloud support for Live API access")
            
            # Try alternative models
            print("\n  Trying alternative models...")
            for model_name in ["models/gemini-2.0-flash", "gemini-2.5-flash"]:
                try:
                    print(f"\n  Testing {model_name}...")
                    async with client.aio.live.connect(
                        model=model_name,
                        config=config
                    ) as session:
                        print(f"  ✓ Success with {model_name}!")
                        return True
                except Exception as e2:
                    print(f"  ❌ Failed with {model_name}: {type(e2).__name__}")
            
            return False
            
    except ImportError as e:
        print(f"❌ FAIL: Cannot import new genai client: {e}")
        print("  The Live API requires google-generativeai >= 0.8.0")
        print("  Upgrade with: pip install --upgrade google-generativeai")
        return False
    except Exception as e:
        print(f"❌ FAIL: Unexpected error: {e}")
        return False


def print_summary(results: dict):
    """Print summary of all tests."""
    print_section("Summary")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"Tests passed: {passed}/{total}\n")
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print("\n" + "="*60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your Gemini API is configured correctly.")
    else:
        print("\n⚠️  Some tests failed. Review the output above for details.")
        print("\nCommon solutions:")
        print("  1. Verify API key at: https://aistudio.google.com/apikey")
        print("  2. Install package: pip install google-genai")
        print("  3. Enable Gemini API in Google Cloud Console")
        print("  4. Check API quotas and billing")
        print("  5. For Live API: Contact Google for experimental access")


async def main():
    """Run all diagnostic tests."""
    print("\n" + "="*60)
    print("  GEMINI API DIAGNOSTIC TOOL")
    print("="*60)
    
    results = {}
    
    # Test 1: API Key
    results["API Key Configuration"] = test_api_key()
    if not results["API Key Configuration"]:
        print("\n⚠️  Cannot proceed without valid API key. Stopping tests.")
        print_summary(results)
        return
    
    # Test 2: Package Installation
    pkg_installed, new_client = test_google_genai_import()
    results["Package Installation"] = pkg_installed
    if not pkg_installed:
        print("\n⚠️  Cannot proceed without package. Stopping tests.")
        print_summary(results)
        return
    
    # Test 3: Basic API Access
    api_works, models = test_basic_api_access()
    results["Basic API Access"] = api_works
    
    # Test 4: Simple Generation
    if api_works:
        results["Simple Generation"] = test_simple_generation()
    else:
        results["Simple Generation"] = False
        print_section("4. Simple Generation Test")
        print("⊘ Skipped due to API access failure")
    
    # Test 5: Live API
    if new_client:
        results["Live API Access"] = await test_live_api()
    else:
        results["Live API Access"] = False
        print_section("5. Live API Test")
        print("⊘ Skipped - new client not available")
    
    # Print summary
    print_summary(results)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Unexpected error running diagnostics: {e}")
        import traceback
        traceback.print_exc()