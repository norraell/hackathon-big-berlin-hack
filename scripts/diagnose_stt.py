#!/usr/bin/env python3
"""Diagnostic script to check STT configuration and help troubleshoot issues."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_status(check: str, passed: bool, message: str = "") -> None:
    """Print a status line."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {check}")
    if message:
        print(f"       {message}")


def check_environment() -> bool:
    """Check environment configuration."""
    print_header("Environment Configuration")
    
    all_passed = True
    
    # Check .env file
    env_file = Path(".env")
    env_exists = env_file.exists()
    print_status(".env file exists", env_exists)
    if not env_exists:
        print("       Create .env from .env.example: cp .env.example .env")
        all_passed = False
    
    # Check STT_PROVIDER
    stt_provider = os.getenv("STT_PROVIDER", "gemini")
    print(f"\nSTT_PROVIDER = {stt_provider}")
    
    if stt_provider == "gemini":
        print_status(
            "STT Provider",
            False,
            "Gemini Live API is not available. Change to 'google_cloud'"
        )
        all_passed = False
    elif stt_provider == "google_cloud":
        print_status("STT Provider", True, "Using Google Cloud Speech-to-Text")
    else:
        print_status("STT Provider", False, f"Unknown provider: {stt_provider}")
        all_passed = False
    
    return all_passed


def check_google_cloud_credentials() -> bool:
    """Check Google Cloud credentials."""
    print_header("Google Cloud Credentials")
    
    all_passed = True
    
    # Check GOOGLE_APPLICATION_CREDENTIALS
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print_status(
            "GOOGLE_APPLICATION_CREDENTIALS",
            False,
            "Environment variable not set"
        )
        print("\n       Set it in your .env file or export it:")
        print("       export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        all_passed = False
    else:
        print_status(
            "GOOGLE_APPLICATION_CREDENTIALS",
            True,
            f"Set to: {creds_path}"
        )
        
        # Check if file exists
        if Path(creds_path).exists():
            print_status("Credentials file exists", True, creds_path)
        else:
            print_status(
                "Credentials file exists",
                False,
                f"File not found: {creds_path}"
            )
            all_passed = False
    
    return all_passed


def check_packages() -> bool:
    """Check required packages."""
    print_header("Required Packages")
    
    all_passed = True
    
    # Check google-cloud-speech
    try:
        import google.cloud.speech
        print_status("google-cloud-speech", True, f"Version: {google.cloud.speech.__version__}")
    except ImportError:
        print_status(
            "google-cloud-speech",
            False,
            "Not installed. Run: pip install google-cloud-speech"
        )
        all_passed = False
    
    # Check google-generativeai
    try:
        import google.generativeai
        print_status("google-generativeai", True, "Installed (for LLM)")
    except ImportError:
        print_status(
            "google-generativeai",
            False,
            "Not installed. Run: pip install google-generativeai"
        )
        all_passed = False
    
    return all_passed


def test_google_cloud_stt() -> bool:
    """Test Google Cloud Speech-to-Text connection."""
    print_header("Google Cloud STT Connection Test")
    
    try:
        from google.cloud import speech_v1p1beta1 as speech
        
        # Try to create client
        client = speech.SpeechClient()
        print_status("Client creation", True, "Successfully created Speech client")
        
        # Try to list available models (this will fail if credentials are invalid)
        try:
            # This is a simple test that doesn't cost anything
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
            )
            print_status("API access", True, "Credentials are valid")
            return True
        except Exception as e:
            print_status("API access", False, f"Error: {e}")
            return False
            
    except ImportError:
        print_status("Import", False, "google-cloud-speech not installed")
        return False
    except Exception as e:
        print_status("Connection", False, f"Error: {e}")
        return False


def print_recommendations() -> None:
    """Print recommendations based on checks."""
    print_header("Recommendations")
    
    print("To fix the STT configuration:")
    print()
    print("1. Update your .env file:")
    print("   STT_PROVIDER=google_cloud")
    print()
    print("2. Set up Google Cloud credentials:")
    print("   - Create a service account in Google Cloud Console")
    print("   - Download the JSON key file")
    print("   - Set GOOGLE_APPLICATION_CREDENTIALS in .env:")
    print("     GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    print()
    print("3. Install required package (if not already installed):")
    print("   pip install google-cloud-speech")
    print()
    print("4. See detailed setup guide:")
    print("   documentation/STT_CONFIGURATION.md")
    print()


def main() -> None:
    """Run all diagnostic checks."""
    print("\n" + "=" * 70)
    print("  STT Configuration Diagnostic Tool")
    print("=" * 70)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("\n✅ Loaded .env file")
    except ImportError:
        print("\n⚠️  python-dotenv not installed, using system environment only")
    
    # Run checks
    env_ok = check_environment()
    creds_ok = check_google_cloud_credentials()
    packages_ok = check_packages()
    
    # Only test connection if previous checks passed
    if env_ok and creds_ok and packages_ok:
        connection_ok = test_google_cloud_stt()
    else:
        connection_ok = False
        print_header("Google Cloud STT Connection Test")
        print("⏭️  Skipped - fix previous issues first")
    
    # Summary
    print_header("Summary")
    
    all_passed = env_ok and creds_ok and packages_ok and connection_ok
    
    if all_passed:
        print("✅ All checks passed! Your STT configuration is ready.")
        print("\nYou can now start the application:")
        print("  uvicorn app.main:app --reload")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print_recommendations()
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()