# Gemini STT Error 1011 - Troubleshooting Guide

## Error Description

```
google.genai.errors.APIError: 1011 None. Internal error encountered.
```

This error occurs when trying to establish a connection to the Google Gemini Live API for speech-to-text streaming.

## Root Causes

The error 1011 (Internal error) from Gemini Live API typically indicates one of the following issues:

### 1. **API Availability Issues**
- The Gemini Live API may not be available in your geographic region
- The API endpoint might be experiencing temporary issues
- Your account may not have access to the Live API features

### 2. **Authentication Problems**
- Invalid or expired API key
- API key doesn't have the necessary permissions for Live API
- API key quota exceeded

### 3. **Model Access Issues**
- The model `gemini-2.0-flash-exp` may not be accessible with your API key
- The model might be in experimental/preview status with limited access
- Model name might have changed or been deprecated

### 4. **Configuration Problems**
- Incorrect API configuration parameters
- Missing required configuration fields
- Incompatible audio format or settings

## Solutions

### Solution 1: Verify Your API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Generate a new API key or verify your existing one
3. Update your `.env` file:
   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   ```

### Solution 2: Check API Access

1. Verify that your Google Cloud project has the Gemini API enabled
2. Check if you have access to the Live API features
3. Review your API quota and usage limits

### Solution 3: Try Alternative Models

The code has been updated to use `gemini-2.0-flash-exp`, but you can try other models:

```python
# In app/stt/gemini_stt.py, line ~95
self._session_ctx = self.client.aio.live.connect(
    model="models/gemini-2.5-flash",  # Try: gemini-pro, gemini-2.5-flash, etc.
    config=config
)
```

### Solution 4: Use Standard Gemini API (Fallback)

If the Live API is not available, consider using the standard Gemini API with batch processing instead of streaming:

```python
# Alternative implementation using standard API
import google.generativeai as genai

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel('gemini-pro')
response = model.generate_content("Your audio transcription request")
```

### Solution 5: Check Regional Availability

The Gemini Live API may have regional restrictions. Try:

1. Using a VPN to test from different regions
2. Checking Google's documentation for API availability in your region
3. Contacting Google Cloud support for access

## Code Changes Made

The `app/stt/gemini_stt.py` file has been updated with:

1. **Better Error Handling**: Detailed error messages explaining possible causes
2. **Proper Session Management**: Correct async context manager usage
3. **Resource Cleanup**: Proper cleanup of sessions and tasks
4. **Robust Response Processing**: Handles various response formats from Gemini

### Key Improvements:

```python
# Proper session initialization with error handling
try:
    self._session_ctx = self.client.aio.live.connect(
        model="models/gemini-2.0-flash-exp",
        config=config
    )
    self._session = await self._session_ctx.__aenter__()
except Exception as e:
    if "1011" in str(e) or "Internal error" in str(e):
        raise RuntimeError(
            "Gemini Live API returned internal error (1011). This may be due to:\n"
            "1. API not available in your region\n"
            "2. Invalid API key or insufficient permissions\n"
            "3. Model 'gemini-2.0-flash-exp' not accessible\n"
            "4. Live API not enabled for your account"
        ) from e
```

## Testing Your Configuration

1. **Test API Key**:
   ```bash
   python -c "from google import genai; client = genai.Client(api_key='YOUR_KEY'); print('API key valid')"
   ```

2. **Check Available Models**:
   ```python
   from google import genai
   client = genai.Client(api_key='YOUR_KEY')
   models = client.models.list()
   for model in models:
       print(model.name)
   ```

3. **Test Basic Gemini Access**:
   ```python
   import google.generativeai as genai
   genai.configure(api_key='YOUR_KEY')
   model = genai.GenerativeModel('gemini-pro')
   response = model.generate_content("Hello")
   print(response.text)
   ```

## Alternative STT Solutions

If Gemini Live API continues to fail, consider these alternatives:

1. **Google Cloud Speech-to-Text**: More stable, production-ready API
2. **OpenAI Whisper**: Open-source, can run locally
3. **AssemblyAI**: Commercial alternative with good streaming support
4. **Azure Speech Services**: Microsoft's speech-to-text API

## Getting Help

If the issue persists:

1. Check [Google AI Studio Status](https://status.cloud.google.com/)
2. Review [Gemini API Documentation](https://ai.google.dev/docs)
3. Post in [Google AI Developer Forum](https://discuss.ai.google.dev/)
4. Contact Google Cloud Support if you have a support plan

## Environment Variables Checklist

Ensure your `.env` file has:

```bash
# Required
GEMINI_API_KEY=your_actual_api_key_here

# Optional but recommended
DEFAULT_LANGUAGE=en
SUPPORTED_LANGUAGES=en,de,es,fr,pt
LOG_LEVEL=DEBUG  # For troubleshooting
```

## Debugging Tips

1. **Enable Debug Logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Check Logs**: Look for detailed error messages in your application logs

3. **Test Incrementally**: Start with basic API calls before trying Live API

4. **Monitor API Usage**: Check your Google Cloud Console for API usage and errors

## Next Steps

1. Verify your API key is valid and has proper permissions
2. Check if Gemini Live API is available in your region
3. Try alternative models if the experimental model is not accessible
4. Consider using the standard Gemini API as a fallback
5. Contact Google Cloud support if you have enterprise access

---

**Last Updated**: 2026-04-25
**Status**: Active troubleshooting guide