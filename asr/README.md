# ASR Module — Setup Guide

This module transcribes YouTube video audio to text using **faster-whisper** (Whisper + CTranslate2). It can run on **GPU** (default) or **CPU**, and is used by the AiCourseBuilder backend when captions are not available.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | 3.9 or higher |
| **FFmpeg** | On your system `PATH` (used by yt-dlp to extract audio). [Download](https://ffmpeg.org/download.html) if needed. |
| **GPU (optional)** | NVIDIA GPU with CUDA for faster transcription. Works on CPU if no GPU or if you set `ASR_DEVICE=cpu`. |

---

## Quick setup (5 steps)

### 1. Open a terminal in the project

From the repo root (e.g. `AiCourseBuilder_v1`), go into the `asr` folder:

```bash
cd asr
```

### 2. Create a virtual environment

**Windows (PowerShell or CMD):**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your prompt.

### 3. Install dependencies

With the venv active:

```bash
pip install -r requirements.txt
```

The first run may take a few minutes (downloads the Whisper model on first use).

### 4. Verify FFmpeg

yt-dlp needs FFmpeg to convert audio. Check that it’s available:

```bash
ffmpeg -version
```

If that fails, install FFmpeg and add it to your `PATH`.

### 5. Test the setup

**Device check only (no download):**

```bash
python test_transcribe.py
```

**Full test with a short YouTube video:**

```bash
python transcribe.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The transcript is printed after `===TRANSCRIPT===` and also saved to `asr/transcript_output.txt`.

---

## Usage

### Command line

```bash
python transcribe.py <youtube_url>
```

Example:

```bash
python transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASR_DEVICE` | `cuda` | `cuda` = use GPU, `cpu` = use CPU only. |
| `ASR_COMPUTE` | (auto) | GPU: `int8_float16`; CPU: `int8`. Override with `float32`, `float16`, or `int8_float16` if needed. |
| `ASR_MODEL` | `small` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3`. |
| `ASR_VAD_FILTER` | `1` | `0` = disable VAD (can help if GPU crashes at ~30s). |
| `ASR_BEAM_SIZE` | `5` | Lower (e.g. `3`) reduces memory use on GPU. |

**Force CPU:**

```bash
# Windows
set ASR_DEVICE=cpu
python transcribe.py "https://youtube.com/watch?v=..."

# macOS / Linux
ASR_DEVICE=cpu python transcribe.py "https://youtube.com/watch?v=..."
```

---

## Output

- **Terminal:** Logs and progress, then a line `===TRANSCRIPT===` followed by the full transcript text.
- **File:** The same transcript is written to `asr/transcript_output.txt` every run.

The backend parses the transcript from the script output; the file is a backup you can open anytime.

---

## GPU issues (Windows)

If transcription crashes with **exit code 3221226505** (or the process exits unexpectedly on GPU):

1. The script already uses a more stable GPU setup (e.g. `int8_float16`, DLL paths). Try running as-is first.
2. If it still crashes, see **[ASR_GPU_SETUP.md](./ASR_GPU_SETUP.md)** for:
   - Copying required DLLs (e.g. `zlibwapi.dll`, cuDNN) into the ctranslate2 folder
   - Using `ASR_COMPUTE=float32` or disabling VAD
   - CUDA 11 / cuDNN 8 note: `pip install ctranslate2==4.4.0` after the main install

To force CPU and avoid GPU entirely:

```bash
set ASR_DEVICE=cpu
python transcribe.py "<url>"
```

---

## Testing & performance metrics

For **RTF**, **WER/CER**, **ROUGE/BERTScore**, and **faithfulness** see **[TESTING.md](./TESTING.md)**. It covers:

- `benchmark_transcribe.py` — Real-Time Factor, throughput (words/s), VRAM/RAM, confidence
- `metrics_accuracy.py` — Word/Character Error Rate vs reference transcript (jiwer)
- `course_quality_metrics.py` — ROUGE, BERTScore, faithfulness (generated vs transcript)
- Backend **TTFT** (time to first lesson) via SSE event `ttft`

---

## Files in this folder

| File | Purpose |
|------|---------|
| `transcribe.py` | Main script: download audio from URL → transcribe → print and save transcript. |
| `test_transcribe.py` | Checks GPU/CPU and optionally runs a full transcription. |
| `benchmark_transcribe.py` | Performance: RTF, throughput, RAM/VRAM, confidence (see TESTING.md). |
| `metrics_accuracy.py` | WER/CER vs reference transcript (requires jiwer). |
| `course_quality_metrics.py` | ROUGE, BERTScore, faithfulness for generated content. |
| `requirements.txt` | Python dependencies (faster-whisper, yt-dlp, tqdm, etc.). |
| `ASR_GPU_SETUP.md` | Detailed GPU troubleshooting and DLL setup. |
| `TESTING.md` | Testing workflow and metric definitions. |
| `transcript_output.txt` | Last transcript output (created when you run `transcribe.py`). |

---

## Integration with AiCourseBuilder

The backend runs this module when:

- It needs a transcript for a lesson and YouTube captions are not available.
- It calls: `python -u asr/transcribe.py <youtube_url>` (using the repo’s `asr` path and optional venv Python).
- It reads the transcript from the script’s stdout (after `===TRANSCRIPT===`) or, on failure, from `asr/transcript_output.txt` if present.

No extra configuration is required in the app if the ASR setup above works in the terminal.
