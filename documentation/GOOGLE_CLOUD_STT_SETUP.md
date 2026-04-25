# Google Cloud Speech-to-Text Setup Guide

This guide will help you set up Google Cloud Speech-to-Text as an alternative to the Gemini Live API for real-time speech transcription.

## Why Google Cloud Speech-to-Text?

- ✅ **Production-ready**: Stable and battle-tested
- ✅ **Real-time streaming**: Supports bidirectional audio streaming
- ✅ **Telephony optimized**: Has a `phone_call` model specifically for telephony
- ✅ **125+ languages**: Extensive language support
- ✅ **High accuracy**: Industry-leading transcription quality
- ✅ **Similar to Gemini**: Easy migration path when Gemini Live API becomes available

## Prerequisites

- Google Cloud account
- Billing enabled on your Google Cloud project
- Basic familiarity with Google Cloud Console

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "claims-intake-stt")
4. Click "Create"

## Step 2: Enable Speech-to-Text API

1. In Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for "Cloud Speech-to-Text API"
3. Click on it and click **Enable**
4. Wait for the API to be enabled (takes a few seconds)

## Step 3: Create Service Account

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Enter details:
   - **Name**: `stt-service-account`
   - **Description**: `Service account for Speech-to-Text API`
4. Click **Create and Continue**
5. Grant role: **Cloud Speech Client** or **Cloud Speech Administrator**
6. Click **Continue** → **Done**

## Step 4: Create and Download Credentials

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** → **Create new key**
4. Choose **JSON** format
5. Click **Create**
6. Save the downloaded JSON file securely (e.g., `credentials/gcp-stt-key.json`)

⚠️ **Important**: Never commit this file to version control!

## Step 5: Set Up Environment Variables

### Option A: Using Environment Variable (Recommended)

Add to your `.env` file:

```bash
# Google Cloud Speech-to-Text Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials/gcp-stt-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
```

### Option B: Using gcloud CLI

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Set project
gcloud config set project your-project-id
```

## Step 6: Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Google Cloud Speech
pip install google-cloud-speech==2.28.0

# Or install all requirements
pip install -r requirements.txt
```

## Step 7: Update Configuration

Update your `app/config.py` to include Google Cloud settings (if needed):

```python
# Google Cloud Configuration (optional - uses GOOGLE_APPLICATION_CREDENTIALS by default)
google_cloud_project: str = Field(
    default="",
    description="Google Cloud Project ID"
)
```

## Step 8: Update Code to Use Google Cloud STT

Replace the Gemini STT import in your code:

```python
# OLD (Gemini - not available)
from app.stt.gemini_stt import GeminiSTTHandler

# NEW (Google Cloud - production ready)
from app.stt.google_cloud_stt import GoogleCloudSTTHandler

# Usage remains the same
stt_handler = GoogleCloudSTTHandler(
    language="en",
    on_transcript=handle_interim_transcript,
    on_final=handle_final_transcript
)
```

## Step 9: Test the Setup

Create a test script `scripts/test_google_cloud_stt.py`:

```python
#!/usr/bin/env python3
"""Test Google Cloud Speech-to-Text setup."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.stt.google_cloud_stt import GoogleCloudSTTHandler


async def test_stt():
    """Test STT initialization."""
    
    def on_transcript(text, confidence, language):
        print(f"Interim: {text} ({confidence:.2f})")
    
    def on_final(text, confidence, language):
        print(f"Final: {text} ({confidence:.2f})")
    
    handler = GoogleCloudSTTHandler(
        language="en",
        on_transcript=on_transcript,
        on_final=on_final
    )
    
    try:
        await handler.start()
        print("✓ STT handler started successfully!")
        
        # Keep alive for a few seconds
        await asyncio.sleep(2)
        
        await handler.stop()
        print("✓ STT handler stopped successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_stt())
```

Run the test:

```bash
python scripts/test_google_cloud_stt.py
```

## Pricing

Google Cloud Speech-to-Text pricing (as of 2024):

- **Standard model**: $0.006 per 15 seconds
- **Enhanced model**: $0.009 per 15 seconds
- **First 60 minutes per month**: FREE

For a typical call:
- 5-minute call = 20 × 15-second chunks = $0.12 (standard) or $0.18 (enhanced)
- 100 calls/day = $12/day (standard) or $18/day (enhanced)

💡 **Tip**: Use the standard model for development, enhanced for production.

## Troubleshooting

### Error: "Could not load credentials"

**Solution**: Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to the correct JSON file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/full/path/to/credentials.json"
```

### Error: "Permission denied"

**Solution**: Ensure your service account has the correct role:
1. Go to IAM & Admin → IAM
2. Find your service account
3. Add role: **Cloud Speech Client**

### Error: "API not enabled"

**Solution**: Enable the Speech-to-Text API:
1. Go to APIs & Services → Library
2. Search for "Cloud Speech-to-Text API"
3. Click Enable

### Error: "Quota exceeded"

**Solution**: Check your quota limits:
1. Go to IAM & Admin → Quotas
2. Search for "Speech-to-Text"
3. Request quota increase if needed

## Security Best Practices

1. **Never commit credentials**: Add to `.gitignore`:
   ```
   credentials/
   *-key.json
   *.json
   ```

2. **Use service accounts**: Don't use personal credentials in production

3. **Rotate keys regularly**: Create new keys every 90 days

4. **Limit permissions**: Use principle of least privilege

5. **Monitor usage**: Set up billing alerts in Google Cloud Console

## Migration Path

When Gemini Live API becomes available:

1. Keep Google Cloud STT as fallback
2. Implement feature flag to switch between services
3. Test Gemini Live API in development
4. Gradually migrate production traffic
5. Monitor quality and latency metrics

Example feature flag:

```python
# In config.py
use_gemini_live_api: bool = Field(
    default=False,
    description="Use Gemini Live API instead of Google Cloud STT"
)

# In your code
if settings.use_gemini_live_api:
    from app.stt.gemini_stt import GeminiSTTHandler as STTHandler
else:
    from app.stt.google_cloud_stt import GoogleCloudSTTHandler as STTHandler
```

## Additional Resources

- [Google Cloud Speech-to-Text Documentation](https://cloud.google.com/speech-to-text/docs)
- [Python Client Library](https://cloud.google.com/python/docs/reference/speech/latest)
- [Streaming Recognition Guide](https://cloud.google.com/speech-to-text/docs/streaming-recognize)
- [Best Practices](https://cloud.google.com/speech-to-text/docs/best-practices)
- [Pricing Calculator](https://cloud.google.com/products/calculator)

## Support

- **Google Cloud Support**: https://cloud.google.com/support
- **Community Forum**: https://stackoverflow.com/questions/tagged/google-cloud-speech
- **Issue Tracker**: https://issuetracker.google.com/issues?q=componentid:187143

---

**Status**: Production-ready alternative to Gemini Live API  
**Setup Time**: ~15 minutes  
**Cost**: ~$0.006 per 15 seconds (with free tier)  
**Recommended**: ✅ Yes, for immediate use