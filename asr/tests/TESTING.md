# ASR & Course Generation Testing & Metrics

This document describes how to measure **transcription performance**, **accuracy**, and **course content quality** using the provided scripts and optional backend events.

---

## 1. Transcription Efficiency (ASR Performance)

### Metrics

| Metric | Formula | Goal |
|--------|---------|------|
| **Real-Time Factor (RTF)** | Transcription time (s) / Audio duration (s) | **RTF < 1.0** = faster than real-time |
| **Throughput** | Words (or tokens) per second | Higher = better |
| **VRAM / RAM** | Peak memory during transcription | Monitor for OOM / leaks |
| **Avg confidence** | exp(avg_logprob) from segments | 0–1; higher = more confident |

### Benchmark script

From the `asr` folder with venv active:

```bash
# Benchmark using a local audio file
python benchmark_transcribe.py path/to/audio.wav

# Benchmark using a YouTube URL (downloads audio first)
python benchmark_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Compare CPU vs GPU (run twice with different env)
set ASR_DEVICE=cuda
python benchmark_transcribe.py audio.wav

set ASR_DEVICE=cpu
python benchmark_transcribe.py audio.wav
```

Output (JSON) includes: `rtf`, `words_per_sec`, `audio_duration_sec`, `transcription_time_sec`, `peak_ram_mb`, `peak_vram_mb`, `avg_confidence`, `device`, `compute_type`, `model_size`.

### Dependencies for benchmark

- **psutil**: RAM usage (`pip install psutil`)
- **pynvml**: GPU VRAM (optional; `pip install pynvml`). Without it, `peak_vram_mb` is omitted.

### Recommended workflow

1. **Dataset**: Use 3–5 videos of varying length (e.g. 5 min, 30 min, 1 h).
2. **Cross-hardware**: Run the same URLs with `ASR_DEVICE=cpu` and `ASR_DEVICE=cuda` and compare RTF and VRAM.
3. **Model size**: Try `ASR_MODEL=tiny` (fast) vs `ASR_MODEL=small` (better quality) vs `ASR_MODEL=medium`.

---

## 2. Transcription Accuracy Metrics

These require a **reference (ground truth)** transcript for the same audio.

### Word Error Rate (WER) and Character Error Rate (CER)

- **WER** = (S + D + I) / N (substitutions, deletions, insertions over reference word count).
- **CER**: same idea at character level (good for technical terms).

### Accuracy script

```bash
# Hypothesis = system output; reference = ground truth (file paths)
python metrics_accuracy.py --hypothesis transcript.txt --reference reference.txt --hypothesis-is-path --reference-is-path

# Optional: record confidence from a prior benchmark run
python metrics_accuracy.py -H hyp.txt -R ref.txt --hypothesis-is-path --reference-is-path --confidence 0.92 --json
```

**Dependency**: `pip install jiwer`

To get reference transcripts: use YouTube captions (e.g. download via yt-dlp or manual copy) or human transcription.

---

## 3. Course Content Quality Metrics (LLM / Summarization)

Compares **generated** course content (summary/notes) to the **source transcript** and optionally to a **reference summary**.

| Metric | Description |
|--------|-------------|
| **ROUGE (1, 2, L)** | N-gram and longest-common-subsequence overlap with reference summary |
| **BERTScore** | Semantic similarity with reference (contextual embeddings) |
| **Faithfulness** | Fraction of generated content words that appear in the source transcript (0–1; reduces hallucination) |

### Course quality script

```bash
# Faithfulness only (generated vs transcript; no reference summary needed)
python course_quality_metrics.py --transcript transcript.txt --generated summary.txt

# With reference summary (for ROUGE and BERTScore)
python course_quality_metrics.py -T transcript.txt -G summary.txt -R reference_summary.txt

# JSON output
python course_quality_metrics.py -T transcript.txt -G summary.txt -R ref.txt --json
```

**Optional dependencies**:

- `pip install rouge-score`   # for ROUGE
- `pip install bert-score`   # for BERTScore (uses PyTorch and transformers)

Faithfulness is computed by default (no extra packages).

---

## 4. Latency: Time to First Token (TTFT)

Measures how long until the **first lesson content** is available during course generation.

- The **backend** emits an SSE event `ttft` when the first lesson with content is produced.
- Payload: `{ ttft_sec: number, lesson_index: number }`.
- To measure: in the frontend (or a test client), subscribe to the execute SSE stream and record the time from request start until the first `ttft` event.

---

## 5. Quick Reference: Scripts and Env Vars

| Script | Purpose |
|--------|---------|
| `test_transcribe.py` | Device check (GPU/CPU) + optional full pipeline test |
| `benchmark_transcribe.py` | RTF, throughput, RAM/VRAM, confidence (one run) |
| `metrics_accuracy.py` | WER/CER vs reference transcript |
| `course_quality_metrics.py` | ROUGE, BERTScore, faithfulness (generated vs transcript/reference) |

| Env var | Effect |
|---------|--------|
| `ASR_DEVICE` | `cuda` or `cpu` |
| `ASR_COMPUTE` | `int8`, `float16`, `int8_float16`, `float32` |
| `ASR_MODEL` | `tiny`, `base`, `small`, `medium`, `large-v2`, `large-v3` |
| `ASR_BEAM_SIZE` | Beam size (default 5) |
| `ASR_VAD_FILTER` | `1` or `0` |

---

## 6. Install Optional Testing Dependencies

From `asr`:

```bash
pip install jiwer rouge-score bert-score psutil pynvml
```

Or use the same versions as in `requirements.txt` (testing section).
