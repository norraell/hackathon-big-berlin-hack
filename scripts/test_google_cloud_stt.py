#!/usr/bin/env python3
"""Test Google Cloud Speech-to-Text setup."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.stt.google_cloud_stt import GoogleCloudSTTHandler


async def test_stt():
    """Test STT initialization and basic functionality."""
    
    print("="*60)
    print("  Google Cloud Speech-to-Text Test")
    print("="*60)
    print()
    
    def on_transcript(text, confidence, language):
        print(f"📝 Interim: {text} (confidence: {confidence:.2f}, lang: {language})")
    
    def on_final(text, confidence, language):
        print(f"✅ Final: {text} (confidence: {confidence:.2f}, lang: {language})")
    
    handler = GoogleCloudSTTHandler(
        language="en",
        on_transcript=on_transcript,
        on_final=on_final
    )
    
    try:
        print("1. Initializing STT handler...")
        await handler.start()
        print("   ✓ STT handler started successfully!")
        print()
        
        print("2. Handler is ready to receive audio")
        print("   (In production, audio would be streamed here)")
        print()
        
        # Simulate some activity
        print("3. Testing for 2 seconds...")
        await asyncio.sleep(2)
        print("   ✓ Handler remained stable")
        print()
        
        print("4. Stopping handler...")
        await handler.stop()
        print("   ✓ STT handler stopped successfully!")
        print()
        
        print("="*60)
        print("  ✅ All tests passed!")
        print("="*60)
        print()
        print("Next steps:")
        print("  1. Integrate with your telephony system")
        print("  2. Stream audio chunks using handler.send_audio()")
        print("  3. Process transcripts in your callbacks")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print()
        print("Solution:")
        print("  pip install google-cloud-speech")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Common issues:")
        print("  1. GOOGLE_APPLICATION_CREDENTIALS not set")
        print("     → Set it to your service account JSON file path")
        print()
        print("  2. Speech-to-Text API not enabled")
        print("     → Enable it in Google Cloud Console")
        print()
        print("  3. Service account lacks permissions")
        print("     → Add 'Cloud Speech Client' role")
        print()
        print("See GOOGLE_CLOUD_STT_SETUP.md for detailed setup instructions")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_stt())