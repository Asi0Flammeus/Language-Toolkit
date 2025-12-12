# Video Merge CLI

Creates videos from matched MP3/PNG file pairs.

## Basic Usage

```bash
# Single directory
python video_merge_cli.py -i ./slides -o ./output

# Recursive processing
python video_merge_cli.py -i ./languages -o ./videos --recursive

# With intro video
python video_merge_cli.py -i ./input -o ./output --intro
```

## Running as Background Process

Use the `--log` flag to write progress to a file, then run with `&`:

```bash
# Start in background with log file
python video_merge_cli.py -i ./input -o ./output --recursive --log progress.log &

# Monitor progress in real-time
tail -f progress.log
```

The log file receives timestamped output showing:
- File matching progress
- Video creation status
- Errors and warnings
- Final summary

### Using nohup (survives terminal close)

```bash
nohup python video_merge_cli.py -i ./input -o ./output --recursive --log progress.log &
tail -f progress.log
```

### Check if still running

```bash
ps aux | grep video_merge_cli
```

## Options

| Flag | Description |
|------|-------------|
| `-i, --input` | Input folder with MP3/PNG files (required) |
| `-o, --output` | Output folder for videos (required) |
| `-r, --recursive` | Process subdirectories |
| `--intro` | Add Plan B intro video |
| `--intro-path PATH` | Custom intro video path |
| `--no-skip` | Overwrite existing output files |
| `--log PATH` | Log file for progress output |
| `-v, --verbose` | Enable debug logging |

## File Matching

Files are matched by a **2-digit index** in their names:

```
slide_01_title.png   <-->  audio_01_narrator.mp3
lesson-02-intro.png  <-->  lesson-02-speech.mp3
```

The CLI skips directories where PNG/MP3 counts don't match.

## Output

- Videos are named after the first MP3 file (with index and voice names removed)
- By default, existing outputs are skipped (use `--no-skip` to overwrite)
