# Translation Providers System

## Overview

The Language Toolkit now supports **multiple translation providers** that are automatically selected based on the target language. The system uses `language_provider.json` to determine which provider to use for each language.

## Supported Providers

### 1. DeepL (High-Quality European Languages)
- **Best for**: Most European languages
- **Languages**: Czech, German, English, Spanish, Estonian, Finnish, French, Indonesian, Italian, Japanese, Korean, Norwegian, Dutch, Polish, Portuguese, Romanian, Russian, Swedish, Turkish, Chinese (Simplified & Traditional)
- **API Key**: `DEEPL_API_KEY` environment variable
- **Website**: https://www.deepl.com/pro-api

### 2. Google Translate (Broad Language Support)
- **Best for**: Languages not supported by DeepL
- **Languages**: Hindi, Rundi, Swahili, Vietnamese
- **API Key**: `GOOGLE_API_KEY` environment variable
- **Setup**: Enable Translation API at https://console.cloud.google.com/apis/library/translate.googleapis.com
- **Website**: https://cloud.google.com/translate

### 3. OpenAI (Context-Aware Translation)
- **Best for**: Languages requiring nuanced understanding
- **Languages**: Farsi, Sinhala, Serbian (Latin), Thai
- **API Key**: `OPENAI_API_KEY` environment variable
- **Model**: Uses GPT-4o-mini for cost-effective, high-quality translation
- **Website**: https://platform.openai.com/

## Configuration

### Environment Variables

Add your API keys to `.env` file:

```bash
# At least one is required
DEEPL_API_KEY=your-deepl-key-here
GOOGLE_API_KEY=your-google-key-here
OPENAI_API_KEY=your-openai-key-here
```

### Language Provider Configuration

The system uses `language_provider.json` to map languages to providers:

```json
{
  "languages": [
    {
      "code": "fr",
      "name": "French",
      "translator": "deepl",
      "code_translator": "FR"
    },
    {
      "code": "hi",
      "name": "Hindi",
      "translator": "google",
      "code_translator": "HI"
    },
    {
      "code": "fa",
      "name": "Farsi",
      "translator": "openai",
      "code_translator": "FA"
    }
  ]
}
```

## How It Works

### Automatic Provider Selection

1. User requests translation from English to Hindi
2. System looks up Hindi in `language_provider.json`
3. Finds `"translator": "google"`
4. Routes request to Google Translate API
5. Maps language code: `hi` → `HI` (Google format)
6. Returns translated text

### Code Mapping

Each provider has different language code formats:

- **DeepL**: Uppercase with variants (e.g., `EN-US`, `ZH-HANS`)
- **Google**: Lowercase or mixed case (e.g., `zh-CN`, `pt`)
- **OpenAI**: Full language names (e.g., `Chinese Simplified`)

The system automatically handles code conversion.

## Usage Examples

### Text Translation

```python
from core.text_translation import TextTranslationCore
from pathlib import Path

# Initialize (will use environment variables)
translator = TextTranslationCore()

# Translate a file
success = translator.translate_text_file(
    input_path=Path("document.txt"),
    output_path=Path("translated.txt"),
    source_lang="en",
    target_lang="hi"  # Will use Google Translate
)

# Translate a string
result = translator.translate_text(
    text="Hello, world!",
    source_lang="en",
    target_lang="fa"  # Will use OpenAI
)
```

### PPTX Translation

```python
from core.pptx_translation import PPTXTranslationCore
from pathlib import Path

# Initialize
translator = PPTXTranslationCore(api_key="any-provider-key")

# Translate presentation
success = translator.translate_pptx(
    input_path=Path("presentation.pptx"),
    output_path=Path("translated.pptx"),
    source_lang="en",
    target_lang="zh-Hans"  # Will use DeepL
)
```

### API Usage

```bash
# Text translation (will automatically use correct provider)
curl -X POST http://localhost:8000/api/translate-text \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.txt" \
  -F "source_lang=en" \
  -F "target_lang=sw"  # Swahili uses Google Translate

# PPTX translation
curl -X POST http://localhost:8000/api/translate-pptx \
  -F "file=@presentation.pptx" \
  -F "source_lang=en" \
  -F "target_lang=th"  # Thai uses OpenAI
```

## Testing

### Quick Test

1. Set up environment variables in `.env`:
   ```bash
   DEEPL_API_KEY=your-key
   GOOGLE_API_KEY=your-key
   OPENAI_API_KEY=your-key
   ```

2. Create a test file:
   ```bash
   echo "Hello, how are you?" > test.txt
   ```

3. Test with Python:
   ```python
   from core.text_translation import TextTranslationCore
   from pathlib import Path

   translator = TextTranslationCore()

   # Test DeepL (French)
   translator.translate_text_file(
       Path("test.txt"),
       Path("test_fr.txt"),
       "en", "fr"
   )

   # Test Google (Hindi)
   translator.translate_text_file(
       Path("test.txt"),
       Path("test_hi.txt"),
       "en", "hi"
   )

   # Test OpenAI (Farsi)
   translator.translate_text_file(
       Path("test.txt"),
       Path("test_fa.txt"),
       "en", "fa"
   )
   ```

### Check Available Providers

```python
translator = TextTranslationCore()
print("Available providers:", translator.get_available_providers())
# Output: ['deepl', 'google', 'openai']

print("Supported languages:", translator.get_supported_languages())
# Output: {'all': [...], 'by_provider': {...}}
```

## Troubleshooting

### "No translation providers available"

**Cause**: No API keys configured

**Solution**:
1. Check `.env` file exists
2. Verify at least one API key is set
3. Restart the application

### "Provider 'deepl' not available for language"

**Cause**: DeepL key not configured, but language requires DeepL

**Solution**:
1. Add `DEEPL_API_KEY` to `.env`, OR
2. Change language provider in `language_provider.json` to `"google"` or `"openai"`

### "Google API key is invalid"

**Cause**: Google Translate API not enabled

**Solution**:
1. Go to https://console.cloud.google.com/apis/library/translate.googleapis.com
2. Enable the Cloud Translation API
3. Create/use API key with Translation API access

### Translation uses wrong provider

**Cause**: `language_provider.json` configuration

**Solution**:
1. Check `language_provider.json`
2. Update `"translator"` field for the language
3. Restart application

## Adding New Languages

To add a new language:

1. Edit `language_provider.json`:
   ```json
   {
     "code": "ur",
     "name": "Urdu",
     "translator": "google",
     "code_translator": "UR"
   }
   ```

2. Choose appropriate provider:
   - Use `deepl` if supported (check https://www.deepl.com/docs-api/translate-text)
   - Use `google` for broad language support
   - Use `openai` for best quality (higher cost)

3. Find provider-specific code:
   - **DeepL**: Use uppercase (e.g., `"UR"`, `"PT-BR"`)
   - **Google**: Use lowercase (e.g., `"ur"`, `"pt-br"`)
   - **OpenAI**: Use full name (e.g., `"Urdu"`)

## Cost Considerations

### DeepL
- **Pricing**: ~$20/month for 500K characters
- **Best for**: European languages (highest quality)

### Google Translate
- **Pricing**: $20 per 1M characters
- **Best for**: Cost-effective, broad language support

### OpenAI
- **Pricing**: ~$0.15 per 1M input tokens + $0.60 per 1M output tokens
- **Best for**: Languages requiring context, ~$1 per 1M characters
- **Note**: More expensive but better for nuanced translation

## Migration from Old System

### Before (DeepL only)
```python
from core.text_translation import TextTranslationCore

translator = TextTranslationCore(api_key="deepl-key")
translator.translate_text_file(...)
```

### After (Multi-provider)
```python
from core.text_translation import TextTranslationCore

# Option 1: Use environment variables (recommended)
translator = TextTranslationCore()

# Option 2: Pass single key (backward compatible)
translator = TextTranslationCore(api_key="deepl-key")

# Option 3: Pass all keys explicitly
translator = TextTranslationCore(
    deepl_api_key="key1",
    google_api_key="key2",
    openai_api_key="key3"
)

# Same API, but now automatically uses correct provider
translator.translate_text_file(...)
```

**No code changes required!** The system is backward compatible.

## Architecture

```
User Request
    ↓
TextTranslationCore / PPTXTranslationCore
    ↓
ConfigBasedTranslator
    ├→ Reads language_provider.json
    ├→ Selects provider (deepl/google/openai)
    ├→ Maps language codes
    └→ Routes to appropriate provider
        ↓
[DeepLTranslator] [GoogleTranslator] [OpenAITranslator]
        ↓
    Translation Result
```

## Files Modified

- `core/text_translation.py` - Updated to use ConfigBasedTranslator
- `core/pptx_translation.py` - Already uses ConfigBasedTranslator
- `core/text_translation_config.py` - Provider routing logic
- `core/text_translation_multi.py` - Provider implementations
- `core/config.py` - Added GOOGLE_API_KEY support
- `.env.example` - Added GOOGLE_API_KEY
- `language_provider.json` - Language-to-provider mapping

## Benefits

✅ **Automatic provider selection** per language
✅ **Backward compatible** with existing code
✅ **Cost optimized** - use cheaper providers where appropriate
✅ **Quality optimized** - use best provider per language
✅ **Fallback support** - if preferred provider unavailable, uses alternative
✅ **Environment-based** configuration - secure API key management
✅ **Simple and effective** - minimal code changes required
