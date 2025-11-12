# ElevenLabs Language Support

## Overview

The Language Toolkit now includes intelligent language filtering for ElevenLabs text-to-speech (TTS) services. Only languages supported by the **ElevenLabs Multilingual V2 model** are available for TTS operations.

## Configuration

### elevenlabs_languages.json

This configuration file maps languages from `language_provider.json` to ElevenLabs TTS support:

```json
{
  "model": "eleven_multilingual_v2",
  "supported_languages": [
    {
      "code": "en",
      "name": "English",
      "supported": true
    },
    {
      "code": "fa",
      "name": "Farsi",
      "supported": false,
      "note": "Not supported by ElevenLabs multilingual v2"
    }
  ]
}
```

### Supported Languages (20 total)

Languages with `"supported": true`:

- 🇬🇧 English (en)
- 🇯🇵 Japanese (ja)
- 🇨🇳 Chinese Simplified (zh-Hans)
- 🇹🇼 Chinese Traditional (zh-Hant)
- 🇩🇪 German (de)
- 🇮🇳 Hindi (hi)
- 🇫🇷 French (fr)
- 🇰🇷 Korean (ko)
- 🇵🇹 Portuguese (pt)
- 🇮🇹 Italian (it)
- 🇪🇸 Spanish (es)
- 🇮🇩 Indonesian (id)
- 🇳🇱 Dutch (nl)
- 🇹🇷 Turkish (tr)
- 🇵🇱 Polish (pl)
- 🇸🇪 Swedish (sv)
- 🇷🇴 Romanian (ro)
- 🇨🇿 Czech (cs)
- 🇫🇮 Finnish (fi)
- 🇷🇺 Russian (ru)

### Unsupported Languages (9 total)

Languages with `"supported": false`:

- Estonian (et)
- Farsi (fa)
- Norwegian (nb-NO)
- Rundi (rn)
- Sinhala (si)
- Serbian Latin (sr-Latn)
- Swahili (sw)
- Thai (th)
- Vietnamese (vi)

## Usage

### Check Language Support

```python
from core.text_to_speech import TextToSpeechCore

tts = TextToSpeechCore(api_key="your-elevenlabs-key")

# Check if a language is supported
if tts.is_language_supported("fr"):
    print("French is supported!")
else:
    print("French is not supported")

# Get all supported languages
supported = tts.get_supported_languages()
print(f"Supported languages: {supported}")
# Output: {'en', 'ja', 'zh-Hans', 'de', 'hi', 'fr', 'ko', ...}
```

### Filter Languages from Provider Config

Get only the languages that are both in `language_provider.json` AND supported by ElevenLabs:

```python
from core.text_to_speech import TextToSpeechCore

tts = TextToSpeechCore(api_key="your-elevenlabs-key")

# Get filtered list
supported_langs = tts.filter_languages_from_provider_config()

for lang in supported_langs:
    print(f"{lang['name']} ({lang['code']}) - Translator: {lang['translator']}")

# Output:
# English (en) - Translator: deepl
# Japanese (ja) - Translator: deepl
# Chinese Simplified (zh-Hans) - Translator: deepl
# ... (20 languages total)
```

### GUI Integration Example

```python
from core.text_to_speech import TextToSpeechCore
import tkinter as tk
from tkinter import ttk

class TTSToolGUI:
    def __init__(self):
        self.tts = TextToSpeechCore(api_key="your-key")

        # Get only supported languages
        supported_langs = self.tts.filter_languages_from_provider_config()

        # Populate language dropdown
        self.lang_combo = ttk.Combobox(
            values=[f"{lang['name']} ({lang['code']})" for lang in supported_langs]
        )

    def validate_selection(self, lang_code: str):
        """Validate language selection before TTS"""
        if not self.tts.is_language_supported(lang_code):
            messagebox.showerror(
                "Unsupported Language",
                f"Language '{lang_code}' is not supported by ElevenLabs"
            )
            return False
        return True
```

### API Integration Example

```python
from core.text_to_speech import TextToSpeechCore
from fastapi import HTTPException

tts = TextToSpeechCore(api_key="your-elevenlabs-key")

@app.post("/api/text-to-speech")
async def generate_speech(text: str, language: str):
    # Validate language support
    if not tts.is_language_supported(language):
        raise HTTPException(
            status_code=400,
            detail=f"Language '{language}' is not supported by ElevenLabs. "
                   f"Supported languages: {', '.join(sorted(tts.get_supported_languages()))}"
        )

    # Process TTS
    result = tts.generate_audio(...)
    return result
```

## How It Works

### 1. Configuration Loading

On initialization, `TextToSpeechCore` loads `elevenlabs_languages.json`:

```python
def __init__(self, api_key: str, ...):
    self.supported_languages = set()
    self._load_language_config()  # Loads elevenlabs_languages.json
    self._load_voices_from_api()   # Loads available voices
```

### 2. Language Validation

Before processing, check if language is supported:

```python
def is_language_supported(self, language_code: str) -> bool:
    """Check against loaded configuration"""
    return language_code in self.supported_languages
```

### 3. Filtered Language List

Get intersection of translation languages and TTS languages:

```python
def filter_languages_from_provider_config(self) -> List[Dict]:
    """
    Returns only languages that are:
    1. In language_provider.json (translation supported)
    2. In elevenlabs_languages.json with supported=true
    """
```

## Benefits

✅ **Prevents errors** - Users can't select unsupported languages

✅ **Clear feedback** - Shows which languages work with TTS

✅ **Easy maintenance** - Update JSON file to add/remove languages

✅ **Consistent UX** - Same language list across GUI and API

✅ **Type safety** - Validation methods with clear return types

## Adding New Languages

### If ElevenLabs adds support for a language:

1. **Update elevenlabs_languages.json**:
   ```json
   {
     "code": "new-lang",
     "name": "New Language",
     "supported": true
   }
   ```

2. **Add to language_provider.json** (if not already there):
   ```json
   {
     "code": "new-lang",
     "name": "New Language",
     "translator": "deepl",
     "code_translator": "NEW-LANG"
   }
   ```

3. **Restart application** - Configuration reloads automatically

4. **Update README table** - Add row to language support matrix

### If removing a language:

1. Change `"supported": false` in elevenlabs_languages.json
2. Add a `"note"` field explaining why
3. Update README table with ❌ in TTS column

## Troubleshooting

### Issue: Language shows as unsupported but should work

**Solution**: Check elevenlabs_languages.json:
- Verify `"supported": true`
- Verify language code matches language_provider.json exactly
- Case-sensitive: `"zh-Hans"` ≠ `"zh-hans"`

### Issue: All languages are allowed (no filtering)

**Cause**: elevenlabs_languages.json not found or failed to load

**Solution**:
1. Verify file exists at project root: `elevenlabs_languages.json`
2. Check file is valid JSON (use a validator)
3. Review logs for loading errors

### Issue: Language is in config but not showing in GUI

**Cause**: Either:
- Not in language_provider.json
- Has `"supported": false`

**Solution**: Add to both files with `"supported": true`

## Technical Details

### File Locations

```
Language-Toolkit/
├── elevenlabs_languages.json       # TTS language support config
├── language_provider.json          # Translation language config
└── core/
    └── text_to_speech.py          # TTS implementation with filtering
```

### Configuration Schema

**elevenlabs_languages.json**:
```json
{
  "model": "eleven_multilingual_v2",
  "description": "ElevenLabs Multilingual V2 model language support",
  "supported_languages": [
    {
      "code": "en",           // Matches language_provider.json
      "name": "English",      // Human-readable name
      "elevenlabs_variants": ["USA", "UK", "..."],  // Optional variants
      "supported": true       // TTS support flag
    }
  ],
  "notes": {
    "Bulgarian": "Supported by ElevenLabs but not in language_provider.json"
  }
}
```

### API Methods

| Method | Returns | Purpose |
|--------|---------|---------|
| `is_language_supported(code)` | `bool` | Check single language |
| `get_supported_languages()` | `Set[str]` | Get all supported codes |
| `filter_languages_from_provider_config()` | `List[Dict]` | Get filtered language list |

## Migration Guide

### Old Code (No Filtering)

```python
# All 29 languages shown, including unsupported ones
languages = load_all_languages()
```

### New Code (With Filtering)

```python
# Only 20 ElevenLabs-supported languages shown
tts = TextToSpeechCore(api_key="...")
languages = tts.filter_languages_from_provider_config()
```

### Backward Compatibility

The system is fully backward compatible:
- If `elevenlabs_languages.json` doesn't exist → all languages allowed (old behavior)
- If file exists → only supported languages shown (new behavior)
- No code changes required in existing tools

## References

- **ElevenLabs Docs**: https://elevenlabs.io/docs
- **Multilingual V2 Model**: https://elevenlabs.io/docs/voices/premade-voices
- **Language Support**: https://elevenlabs.io/docs/languages

## Summary

The ElevenLabs language support system provides:

1. ✅ Clear configuration (`elevenlabs_languages.json`)
2. ✅ Runtime validation (`is_language_supported()`)
3. ✅ Filtered language lists (`filter_languages_from_provider_config()`)
4. ✅ Comprehensive documentation (this file)
5. ✅ README table with visual support matrix

This ensures users only see and can select languages that actually work with ElevenLabs TTS, preventing errors and improving user experience.
