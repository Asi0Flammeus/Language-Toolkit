# SVP CLI Usage Guide

Command-line interface for Sequential Video Processing (SVP) without the GUI.

## Prerequisites

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure API keys in `api_keys.json` or set environment variables:
```bash
export DEEPL_API_KEY="your-key"
export CONVERTAPI_KEY="your-key"
export ELEVENLABS_API_KEY="your-key"
```

## Basic Usage

```bash
./svp_cli.py -i INPUT_FOLDER -o OUTPUT_FOLDER -s SOURCE_LANG -t TARGET_LANG(S)
```

## Arguments

### Required Arguments

- `-i, --input PATH` - Input folder containing PPTX and TXT files
- `-o, --output PATH` - Output folder for processed files
- `-s, --source CODE` - Source language code (e.g., en, es, fr)
- `-t, --targets CODE [CODE ...]` - Target language codes (space-separated) or "all"

### Optional Arguments

- `--mode {full,translate,export}` - Processing mode (default: full)
  - `full`: Complete workflow (translation + export + video generation)
  - `translate`: Translation phase only (PPTX and TXT files)
  - `export`: Export phase only (PNG, TTS, video merge)

- `--intro` - Add Plan B intro video to generated videos
- `--no-skip` - Process all files even if output exists (default: skip existing)
- `--log PATH` - Log file for progress output (useful for `tail -f`)
- `--list-languages` - List all available language codes and exit
- `-v, --verbose` - Enable verbose logging

## Examples

### 1. Translate to French and Spanish
```bash
./svp_cli.py -i ./input -o ./output -s en -t fr es
```

### 2. Translate to ALL available languages
```bash
./svp_cli.py -i ./input -o ./output -s en -t all
```

### 3. Translation phase only (no video generation)
```bash
./svp_cli.py -i ./input -o ./output -s en -t de it --mode translate
```

### 4. Export phase only (assumes files are already translated)
```bash
./svp_cli.py -i ./translated -o ./videos -s en -t fr --mode export --intro
```

### 5. Run in background with progress monitoring
```bash
# Start process in background
./svp_cli.py -i ./input -o ./output -s en -t fr es --log progress.log &

# Monitor progress in real-time
tail -f progress.log
```

### 6. Process multiple languages with intro video
```bash
./svp_cli.py -i ./input -o ./output -s en -t fr de es it --intro
```

### 7. Force reprocessing (don't skip existing files)
```bash
./svp_cli.py -i ./input -o ./output -s en -t fr --no-skip
```

## Available Languages

To see all available language codes:
```bash
./svp_cli.py --list-languages
```

Currently supported languages include:
- cs (Czech)
- de (German)
- en (English)
- es (Spanish)
- et (Estonian)
- fa (Farsi)
- fi (Finnish)
- fr (French)
- hi (Hindi)
- id (Indonesian)
- it (Italian)
- ja (Japanese)
- ko (Korean)
- nb-no (Norwegian)
- nl (Dutch)
- pl (Polish)
- pt (Portuguese)
- rn (Rundi)
- ro (Romanian)
- ru (Russian)
- si (Sinhala)
- sr-latn (Serbian)
- sv (Swedish)
- sw (Swahili)
- th (Thai)
- tr (Turkish)
- vi (Vietnamese)
- zh-hans (Chinese Simplified)
- zh-hant (Chinese Traditional)

## Processing Modes

### Full Mode (default)
Complete workflow including:
1. PPTX translation
2. TXT file translation
3. PNG export from PPTX
4. Text-to-speech generation
5. Video creation with PNG slides and TTS audio

### Translation Mode
Only performs:
1. PPTX translation
2. TXT file translation

Useful when you want to:
- Review translations before generating videos
- Separate translation and video generation steps
- Save time/API costs if you only need translated documents

### Export Mode
Only performs:
1. PNG export from translated PPTX
2. Text-to-speech from translated TXT
3. Video generation

Useful when:
- You already have translated files
- You want to regenerate videos with different settings
- You need to fix video generation issues

## File Structure

The CLI expects input folders with this structure:
```
input/
├── Course-Name/
│   ├── presentation.pptx
│   └── script.txt
├── Another-Course/
│   ├── presentation.pptx
│   └── script.txt
└── ...
```

Output will be organized by language:
```
output/
├── fr/
│   ├── Course-Name/
│   │   ├── presentation.pptx (translated)
│   │   ├── script.txt (translated)
│   │   ├── pngs/ (exported slides)
│   │   ├── audio/ (TTS files)
│   │   └── video.mp4 (final video)
│   └── Another-Course/
│       └── ...
├── es/
│   └── ...
└── ...
```

## Background Processing

For long-running processes, use background execution with logging:

```bash
# Start process
nohup ./svp_cli.py -i ./input -o ./output -s en -t all --log progress.log > /dev/null 2>&1 &

# Save process ID
echo $! > svp_process.pid

# Monitor progress
tail -f progress.log

# Check if still running
ps aux | grep $(cat svp_process.pid)

# Stop if needed
kill $(cat svp_process.pid)
```

## Troubleshooting

### Missing API Keys
```
❌ Missing required API keys for: pptx_translation (DeepL API)
```
**Solution**: Configure API keys in `api_keys.json` or environment variables

### Invalid Language Code
```
❌ Error: Invalid target language: xyz
```
**Solution**: Use `--list-languages` to see valid codes

### Input Folder Not Found
```
❌ Error: Input path does not exist: /path/to/input
```
**Solution**: Verify the input path exists and is a directory

### Permission Denied
```
bash: ./svp_cli.py: Permission denied
```
**Solution**: Make the script executable
```bash
chmod +x svp_cli.py
```

## Performance Tips

1. **Use translation-only mode first** to validate translations before generating videos
2. **Process languages in batches** if processing many languages
3. **Use skip existing** (default) to resume interrupted processes
4. **Monitor system resources** when processing multiple large files
5. **Use separate mode for export** if you need to regenerate videos without retranslating

## Exit Codes

- `0` - Success
- `1` - Error (invalid arguments, missing files, API errors, etc.)

## Notes

- The CLI uses the same core processing logic as the GUI
- Progress messages include timestamps when logging to file
- File handles are flushed immediately for real-time `tail -f` monitoring
- Processing can be interrupted with Ctrl+C (graceful shutdown)
- Error logs are saved to the output folder when errors occur
