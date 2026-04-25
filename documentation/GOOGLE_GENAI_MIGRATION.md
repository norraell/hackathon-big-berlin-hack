# Migration from google.generativeai to google.genai

## Overview

This document describes the migration from the deprecated `google.generativeai` package to the new `google.genai` package.

**Important:** The `google.generativeai` package is no longer maintained and will not receive updates or bug fixes. All projects must migrate to `google.genai` as soon as possible.

## Migration Date

**Completed:** 2026-04-25

## What Changed

### Package Name
- **Old:** `google-generativeai==0.8.3`
- **New:** `google-genai==0.3.0`

### Import Statements
```python
# Old
import google.generativeai as genai
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig

# New
from google import genai
from google.genai import types
```

### API Changes

#### 1. Client Initialization

**Old API:**
```python
import google.generativeai as genai

genai.configure(api_key=api_key)
model = GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=system_prompt,
    tools=tools,
)
chat = model.start_chat(history=[])
```

**New API:**
```python
from google import genai

client = genai.Client(api_key=api_key)
# No persistent chat session - each request is independent
```

#### 2. Generation Configuration

**Old API:**
```python
from google.generativeai.types import GenerationConfig

config = GenerationConfig(
    max_output_tokens=150,
    temperature=0.7,
)
```

**New API:**
```python
from google.genai import types

config = types.GenerateContentConfig(
    max_output_tokens=150,
    temperature=0.7,
    system_instruction=system_prompt,
)
```

#### 3. Content Generation

**Old API:**
```python
response = chat.send_message(
    message,
    generation_config=config,
    stream=True,
)
```

**New API:**
```python
response = client.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents=message,
    config=config,
)
```

#### 4. Model Listing

**Old API:**
```python
models = genai.list_models()
```

**New API:**
```python
models = client.models.list()
```

#### 5. Audio Processing

**Old API:**
```python
model = genai.GenerativeModel(model_name)
response = model.generate_content([
    prompt,
    {
        "mime_type": "audio/pcm",
        "data": audio_b64
    }
])
```

**New API:**
```python
response = client.models.generate_content(
    model=model_name,
    contents=[
        prompt,
        types.Part.from_bytes(
            data=audio_data,
            mime_type="audio/pcm"
        )
    ]
)
```

## Files Modified

### Core Application Files

1. **app/llm/client.py**
   - Migrated from `GenerativeModel` to `genai.Client`
   - Updated generation config to use `types.GenerateContentConfig`
   - Changed from persistent chat sessions to stateless requests
   - Added proper type checking and error handling

2. **app/stt/gemini_stt.py**
   - Updated imports to use new `google.genai` package
   - Changed model initialization to use `genai.Client`
   - Updated audio processing to use `types.Part.from_bytes()`
   - Added availability checks for the new package

### Scripts

3. **scripts/diagnose_gemini.py**
   - Updated all API calls to use new client
   - Changed model listing to use `client.models.list()`
   - Updated generation tests to use new API

4. **scripts/diagnose_stt.py**
   - Updated package check from `google-generativeai` to `google-genai`

### Dependencies

5. **requirements.txt**
   - Replaced `google-generativeai==0.8.3` with `google-genai==0.3.0`

## Installation

To install the new package:

```bash
pip install google-genai==0.3.0
```

Or update all dependencies:

```bash
pip install -r requirements.txt
```

## Breaking Changes

### 1. No Persistent Chat Sessions
The new API does not maintain persistent chat sessions. Instead, conversation history must be managed manually through the messages list.

**Impact:** The `clear_history()` method no longer needs to restart a chat session.

### 2. System Instructions in Config
System instructions are now part of the generation config rather than model initialization.

**Impact:** System prompts must be included in each `GenerateContentConfig`.

### 3. Client-Based Architecture
All operations now go through a `Client` instance rather than module-level functions.

**Impact:** Code must create and maintain a client instance.

### 4. Different Type Hierarchy
The types module has a different structure with new classes like `GenerateContentConfig` and `Part`.

**Impact:** Type hints and imports need updating.

## Testing

After migration, test the following:

1. **LLM Client:**
   ```bash
   python scripts/diagnose_gemini.py
   ```

2. **STT Handler:**
   ```bash
   python scripts/diagnose_stt.py
   ```

3. **Full Application:**
   ```bash
   python -m app.main
   ```

## Rollback Plan

If issues arise, you can temporarily rollback by:

1. Reverting `requirements.txt`:
   ```
   google-generativeai==0.8.3
   ```

2. Reverting the code changes in:
   - `app/llm/client.py`
   - `app/stt/gemini_stt.py`
   - `scripts/diagnose_gemini.py`
   - `scripts/diagnose_stt.py`

However, note that `google.generativeai` is deprecated and will not receive updates.

## References

- [Deprecated Package README](https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md)
- [New google-genai Package](https://pypi.org/project/google-genai/)
- [Google AI Studio](https://aistudio.google.com/)

## Support

For issues related to the migration:
1. Check the diagnostic scripts output
2. Verify API key is valid at https://aistudio.google.com/apikey
3. Ensure the new package is properly installed
4. Review error logs for specific API issues

## Future Considerations

- The new API may introduce additional features not available in the old package
- Monitor the `google-genai` package for updates and new capabilities
- Consider migrating to the Live API for real-time streaming when available