# Speech-to-Text (STT) Configuration Guide

## Overview

This system supports two STT providers:

1. **Gemini STT** (Default) - Uses Google Gemini's multimodal capabilities for audio transcription
2. **Google Cloud STT** (Optional) - Uses Google Cloud Speech-to-Text for streaming transcription

## Gemini STT (Default - No Extra Setup Required)

The default configuration uses Gemini for speech-to-text transcription. This works with just your `GEMINI_API_KEY` - no additional credentials needed!

### How It Works

- Uses Gemini's multimodal model to transcribe audio
- Processes audio in batches (every 3 seconds)
- No streaming, but simpler setup
- Good for development and testing

### Configuration

```bash
# In your .env file:
STT_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
```

That's it! No Google Cloud credentials required.

## Google Cloud STT (Optional - Better for Production)

Google Cloud Speech-to-Text is a production-ready, stable alternative that provides excellent real-time transcription for telephony applications.

### Step 1: Update Your Configuration

Edit your `.env` file and change the STT provider:

```bash
# Change from:
STT_PROVIDER=gemini

# To:
STT_PROVIDER=google_cloud
```

### Step 2: Set Up Google Cloud Credentials

1. **Create a Google Cloud Project** (if you don't have one):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable the Speech-to-Text API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Cloud Speech-to-Text API"
   - Click "Enable"

3. **Create a Service Account**:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Name it (e.g., "claims-stt-service")
   - Grant it the "Cloud Speech Client" role
   - Click "Done"

4. **Download the JSON Key**:
   - Click on your new service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Save the file securely (e.g., `~/gcp-credentials/claims-stt-key.json`)

5. **Set the Environment Variable**:
   
   Add to your `.env` file:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
   ```
   
   Or export it in your shell:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
   ```

### Step 3: Restart Your Application

```bash
# If using Docker
docker-compose down
docker-compose up --build

# If running locally
# Make sure to source your .env or export the variable
python -m uvicorn app.main:app --reload
```

## Verification

You can verify your setup with the test script:

```bash
python scripts/test_google_cloud_stt.py
```

This will:
- Check if credentials are configured
- Test the Google Cloud Speech-to-Text API
- Verify audio processing works correctly

## Comparison: Gemini vs Google Cloud STT

| Feature | Gemini Live API | Google Cloud STT |
|---------|----------------|------------------|
| **Availability** | ❌ Not yet in stable package | ✅ Production-ready |
| **Setup Complexity** | Simple (just API key) | Moderate (service account) |
| **Reliability** | Unknown (experimental) | ✅ Battle-tested |
| **Telephony Optimization** | Unknown | ✅ Phone call model |
| **Language Support** | Good | ✅ Excellent (120+ languages) |
| **Cost** | TBD | Pay-per-use (see pricing) |
| **Documentation** | Limited | ✅ Comprehensive |

## When Will Gemini Live API Be Available?

The Gemini Live API is experimental and requires the newer `google-genai` package, which is not yet stable. Monitor these resources for updates:

- [Google AI Studio](https://aistudio.google.com/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [google-generativeai GitHub](https://github.com/google/generative-ai-python)

## Troubleshooting

### Error: "GOOGLE_APPLICATION_CREDENTIALS not set"

**Solution**: Set the environment variable pointing to your JSON key file.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### Error: "Credentials file not found"

**Solution**: Verify the path is correct and the file exists.

```bash
ls -la $GOOGLE_APPLICATION_CREDENTIALS
```

### Error: "Permission denied" or "403 Forbidden"

**Solution**: Ensure your service account has the "Cloud Speech Client" role:

1. Go to Google Cloud Console
2. Navigate to "IAM & Admin" > "IAM"
3. Find your service account
4. Click "Edit" and add "Cloud Speech Client" role

### Error: "API not enabled"

**Solution**: Enable the Speech-to-Text API:

1. Go to Google Cloud Console
2. Navigate to "APIs & Services" > "Library"
3. Search for "Cloud Speech-to-Text API"
4. Click "Enable"

## Cost Considerations

Google Cloud Speech-to-Text pricing (as of 2024):

- **Standard model**: $0.006 per 15 seconds
- **Enhanced model**: $0.009 per 15 seconds (better for telephony)
- **First 60 minutes per month**: FREE

For a typical insurance claims call (5-10 minutes), costs are minimal:
- 10-minute call = 40 requests × $0.009 = **$0.36 per call**

See [official pricing](https://cloud.google.com/speech-to-text/pricing) for details.

## Additional Resources

- [Google Cloud STT Setup Guide](./GOOGLE_CLOUD_STT_SETUP.md)
- [STT Migration Guide](./STT_MIGRATION_GUIDE.md)
- [Gemini STT Troubleshooting](./GEMINI_STT_TROUBLESHOOTING.md)

## Support

If you encounter issues:

1. Check the logs: `LOG_LEVEL=DEBUG` in your `.env`
2. Run the test script: `python scripts/test_google_cloud_stt.py`
3. Review the documentation in the `documentation/` folder
4. Check Google Cloud Console for API errors

---

**Last Updated**: 2026-04-25  
**Status**: Google Cloud STT is the recommended production solution