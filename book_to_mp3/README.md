# epub to MP3

Convert EPUB books to audiobooks using Microsoft Edge TTS. Extracts text for manual review (with automatic preface filtering) before generating audio.

## Requirements

- Python 3.7+
- Microsoft Edge (Edge TTS uses Edge's speech synthesis)

## Installation

```bash
pip install ebooklib beautifulsoup4 edge-tts
```

## Configuration

Edit the config block at the top of `epub_to_mp3.py`:

| Variable | Description |
|----------|-------------|
| `BOOK_FOLDER` | Folder containing your EPUB files |
| `VOICE_FOLDER` | Output folder for audiobooks |
| `BOOK_NAME` | Name of the book (without `.epub`) |
| `VOICE` | TTS voice (e.g. `en-GB-SoniaNeural`, `zh-CN-YunyangNeural`) |
| `RATE` | Speech rate (e.g. `-15%`) |
| `PITCH` | Speech pitch (e.g. `+0%`) |

Chapters whose title matches `PREFACE_KEYWORDS` (preface, 前言, foreword, etc.) are skipped during extract so the audio flows naturally.

## Usage

### 1. Extract text for review

```bash
python epub_to_mp3.py extract
```

- Reads the EPUB in spine order
- Skips preface/front-matter chapters
- Writes per-chapter `.txt` files to `{OUTPUT_FOLDER}/review/`
- Creates `manifest.txt` listing all chapters

### 2. Review and edit (manual)

- Open `review/` and edit any `chapter_NN.txt` as needed
- Delete or modify chapters before generating audio

### 3. Generate audio

**All chapters:**

```bash
python epub_to_mp3.py generate --all
```

**Single chapter (for quick preview):**

```bash
python epub_to_mp3.py generate --chapter 5
```

## Workflow

```
EPUB → extract → review/*.txt (edit) → generate --all or --chapter N → MP3
```
