# Speech-to-Text Migration Guide

## Overview

This guide explains how to migrate from the non-functional Gemini Live API to Google Cloud Speech-to-Text, and provides a path for future migration back to Gemini when it becomes available.

## Current Situation

### ❌ Gemini Live API (Not Working)
- **Status**: Not available with current API key
- **Error**: 1008 - Model not supported for bidiGenerateContent
- **Cause**: Live API requires special access/allowlisting
- **Timeline**: Unknown when general availability will occur

### ✅ Google Cloud Speech-to-Text (Working Alternative)
- **Status**: Production-ready and stable
- **Features**: Real-time streaming, telephony-optimized
- **Setup Time**: ~15 minutes
- **Cost**: ~$0.006 per 15 seconds (with free tier)

## Migration Steps

### Phase 1: Setup Google Cloud STT (Immediate)

1. **Follow Setup Guide**
   - See [`GOOGLE_CLOUD_STT_SETUP.md`](GOOGLE_CLOUD_STT_SETUP.md) for detailed instructions
   - Create Google Cloud project
   - Enable Speech-to-Text API
   - Create service account and download credentials

2. **Install Dependencies**
   ```bash
   pip install google-cloud-speech==2.28.0
   # Or
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   # Add to .env
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-stt-key.json
   GOOGLE_CLOUD_PROJECT=your-project-id
   ```

4. **Test Setup**
   ```bash
   python scripts/test_google_cloud_stt.py
   ```

### Phase 2: Update Application Code

#### Option A: Direct Replacement (Simple)

Replace imports in your code:

```python
# Before (Gemini - not working)
from app.stt.gemini_stt import GeminiSTTHandler

stt = GeminiSTTHandler(
    language="en",
    on_transcript=handle_interim,
    on_final=handle_final
)

# After (Google Cloud - working)
from app.stt.google_cloud_stt import GoogleCloudSTTHandler

stt = GoogleCloudSTTHandler(
    language="en",
    on_transcript=handle_interim,
    on_final=handle_final
)
```

The API is identical, so no other changes needed!

#### Option B: Feature Flag (Recommended)

Create a flexible solution that allows switching between services:

```python
# In app/config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    stt_provider: str = Field(
        default="google_cloud",
        description="STT provider: 'gemini' or 'google_cloud'"
    )

# In your application code
from app.config import settings

def get_stt_handler(language, on_transcript, on_final):
    """Factory function to get the appropriate STT handler."""
    
    if settings.stt_provider == "gemini":
        from app.stt.gemini_stt import GeminiSTTHandler
        return GeminiSTTHandler(language, on_transcript, on_final)
    elif settings.stt_provider == "google_cloud":
        from app.stt.google_cloud_stt import GoogleCloudSTTHandler
        return GoogleCloudSTTHandler(language, on_transcript, on_final)
    else:
        raise ValueError(f"Unknown STT provider: {settings.stt_provider}")

# Usage
stt = get_stt_handler(
    language="en",
    on_transcript=handle_interim,
    on_final=handle_final
)
```

Then in `.env`:
```bash
# Use Google Cloud STT (current working solution)
STT_PROVIDER=google_cloud

# Or use Gemini (when available)
# STT_PROVIDER=gemini
```

### Phase 3: Deploy and Monitor

1. **Deploy Changes**
   - Update production environment variables
   - Deploy updated code
   - Monitor logs for any issues

2. **Monitor Metrics**
   - Transcription accuracy
   - Latency (should be similar or better)
   - Error rates
   - API costs

3. **Set Up Alerts**
   - Google Cloud billing alerts
   - API quota alerts
   - Error rate monitoring

## API Comparison

| Feature | Gemini Live API | Google Cloud STT |
|---------|----------------|------------------|
| **Availability** | ❌ Not accessible | ✅ Production-ready |
| **Real-time Streaming** | ✅ Yes | ✅ Yes |
| **Telephony Optimized** | ✅ Yes | ✅ Yes (phone_call model) |
| **Languages** | Many | 125+ |
| **Accuracy** | High (expected) | High (proven) |
| **Latency** | Low (expected) | Low (~100-300ms) |
| **Cost** | Unknown | $0.006/15s |
| **Free Tier** | Unknown | 60 min/month |
| **Setup Complexity** | Low | Medium |
| **Documentation** | Limited | Extensive |
| **Support** | Community | Enterprise available |

## Code Changes Summary

### Files Modified
- ✅ [`requirements.txt`](requirements.txt) - Added google-cloud-speech
- ✅ [`.env.example`](.env.example) - Added Google Cloud config
- ✅ [`app/stt/gemini_stt.py`](app/stt/gemini_stt.py) - Updated with better error handling

### Files Created
- ✅ [`app/stt/google_cloud_stt.py`](app/stt/google_cloud_stt.py) - New STT implementation
- ✅ [`GOOGLE_CLOUD_STT_SETUP.md`](GOOGLE_CLOUD_STT_SETUP.md) - Setup guide
- ✅ [`GEMINI_LIVE_API_SOLUTION.md`](GEMINI_LIVE_API_SOLUTION.md) - Root cause analysis
- ✅ [`scripts/test_google_cloud_stt.py`](scripts/test_google_cloud_stt.py) - Test script
- ✅ [`scripts/diagnose_gemini.py`](scripts/diagnose_gemini.py) - Diagnostic tool

### Files to Update (Your Application)
- 🔄 Where you import/use `GeminiSTTHandler`
- 🔄 Your `.env` file (add Google Cloud credentials)

## Future Migration Back to Gemini

When Gemini Live API becomes available:

### Step 1: Verify Access
```bash
python scripts/diagnose_gemini.py
```

Look for:
```
✓ Successfully connected to Live API!
```

### Step 2: Test in Development
```python
# In .env.development
STT_PROVIDER=gemini
```

Test thoroughly before production deployment.

### Step 3: Gradual Rollout

Use feature flags to gradually migrate:

```python
# Route 10% of traffic to Gemini
import random

def get_stt_handler(language, on_transcript, on_final):
    if random.random() < 0.1:  # 10% to Gemini
        provider = "gemini"
    else:
        provider = "google_cloud"
    
    # ... rest of factory function
```

### Step 4: Monitor and Compare

Track metrics for both services:
- Accuracy
- Latency
- Error rates
- User satisfaction
- Cost

### Step 5: Full Migration

Once Gemini proves stable and cost-effective:
```bash
# In .env.production
STT_PROVIDER=gemini
```

## Rollback Plan

If issues occur with Google Cloud STT:

1. **Check Credentials**
   ```bash
   echo $GOOGLE_APPLICATION_CREDENTIALS
   cat $GOOGLE_APPLICATION_CREDENTIALS
   ```

2. **Verify API Enabled**
   - Go to Google Cloud Console
   - Check Speech-to-Text API is enabled

3. **Check Quotas**
   - IAM & Admin → Quotas
   - Look for Speech-to-Text limits

4. **Review Logs**
   ```bash
   # Application logs
   tail -f logs/app.log
   
   # Google Cloud logs
   gcloud logging read "resource.type=global"
   ```

## Cost Optimization

### Tips to Reduce Costs

1. **Use Standard Model**
   - Enhanced model costs 50% more
   - Standard is sufficient for most use cases

2. **Optimize Audio Quality**
   - Send 16kHz audio (not 48kHz)
   - Use LINEAR16 encoding
   - Avoid unnecessary resampling

3. **Batch Processing**
   - For non-real-time use cases, use batch API
   - Costs less than streaming

4. **Set Quotas**
   - Prevent unexpected bills
   - Set daily/monthly limits

5. **Monitor Usage**
   - Set up billing alerts
   - Review usage weekly

## Support and Resources

### Documentation
- [Google Cloud STT Setup](GOOGLE_CLOUD_STT_SETUP.md)
- [Gemini Live API Solution](GEMINI_LIVE_API_SOLUTION.md)
- [Troubleshooting Guide](GEMINI_STT_TROUBLESHOOTING.md)

### Testing
- [Diagnostic Script](scripts/diagnose_gemini.py)
- [STT Test Script](scripts/test_google_cloud_stt.py)

### External Resources
- [Google Cloud STT Docs](https://cloud.google.com/speech-to-text/docs)
- [Gemini API Docs](https://ai.google.dev/docs)
- [Community Forum](https://discuss.ai.google.dev/)

## FAQ

**Q: Will this affect my application's performance?**  
A: No, Google Cloud STT has similar or better latency than expected from Gemini Live API.

**Q: How much will this cost?**  
A: ~$0.006 per 15 seconds. For 100 5-minute calls/day: ~$12/day or $360/month.

**Q: Can I use both services?**  
A: Yes! Use the feature flag approach to run both in parallel.

**Q: When will Gemini Live API be available?**  
A: Unknown. Google hasn't announced general availability timeline.

**Q: Should I wait for Gemini or migrate now?**  
A: Migrate now. Google Cloud STT is production-ready and you can switch back later.

**Q: Will I need to change my code again?**  
A: Minimal changes. Both handlers have the same interface.

---

**Status**: Migration guide complete  
**Recommended Action**: Migrate to Google Cloud STT immediately  
**Estimated Time**: 30-60 minutes for complete migration  
**Risk Level**: Low (well-tested alternative)