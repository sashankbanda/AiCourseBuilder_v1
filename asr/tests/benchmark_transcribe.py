"""
ASR performance benchmarking: RTF, throughput, VRAM/RAM, confidence.
Run from asr folder with venv active. Requires audio file or YouTube URL.

  python benchmark_transcribe.py <audio.wav>
  python benchmark_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID"
  ASR_DEVICE=cpu python benchmark_transcribe.py audio.wav   # compare CPU vs GPU

Outputs: Real-Time Factor (RTF), tokens/s (words/s), peak memory, avg confidence.
"""
import os
import sys
import time
import json
import glob
import uuid

# Unbuffered output (Python 3.7+)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

# --- Tier 3: DLL search path (Windows) before any ctranslate2/CUDA load ---
def _setup_dll_search_paths():
    """Add CUDA/ctranslate2 dirs to DLL search path to reduce 0xC0000005 (missing zlibwapi/cuDNN)."""
    if sys.platform != "win32":
        return
    try:
        add_dll = getattr(os, "add_dll_directory", None)
        if not add_dll:
            return
        # 1) Prefer ctranslate2 package dir (user can copy zlibwapi.dll + cuDNN here)
        # Tests are in asr/tests, venv is in asr/venv (one level up)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        venv_lib = os.path.join(parent_dir, "venv", "Lib", "site-packages", "ctranslate2")
        if os.path.isdir(venv_lib):
            add_dll(venv_lib)
        # 2) CUDA Toolkit (common install paths)
        cuda_path = os.getenv("CUDA_PATH", "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.0")
        for sub in ("bin", "bin64", ""):
            d = os.path.join(cuda_path, sub) if sub else cuda_path
            if os.path.isdir(d):
                add_dll(d)
        # CUDA 11 fallback
        cuda11 = "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v11.8"
        if os.path.isdir(cuda11):
            add_dll(os.path.join(cuda11, "bin"))
    except Exception:
        pass


_setup_dll_search_paths()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_memory_mb():
    """Peak process RAM in MB (approximate)."""
    try:
        import psutil
        p = psutil.Process(os.getpid())
        return p.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


def get_gpu_memory_mb():
    """Peak GPU VRAM in MB if available."""
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(h)
        pynvml.nvmlShutdown()
        return info.used / (1024 * 1024)
    except Exception:
        return None


def download_audio(url: str, output_base: str):
    import yt_dlp
    output_template = f"{output_base}.%(ext)s"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    for p in [f"{output_base}.wav", *glob.glob(f"{output_base}*.wav")]:
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def run_benchmark(audio_path: str, device: str, compute_type: str, model_size: str):
    from faster_whisper import WhisperModel

    print(f"Loading model {model_size} on {device} ({compute_type})...", file=sys.stderr, flush=True)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    mem_before_ram = get_memory_mb()
    mem_before_gpu = get_gpu_memory_mb() if device == "cuda" else None

    print("Transcribing (timed)...", file=sys.stderr, flush=True)
    start_time = time.perf_counter()
    segments, info = model.transcribe(
        audio_path,
        beam_size=int(os.getenv("ASR_BEAM_SIZE", "5")),
        task="translate",
        vad_filter=os.getenv("ASR_VAD_FILTER", "1") == "1",
    )
    segments = list(segments)
    end_time = time.perf_counter()

    transcription_time = end_time - start_time
    audio_duration = getattr(info, "duration", None) or 0.0
    if audio_duration <= 0 and segments:
        # Fallback: estimate from last segment end
        audio_duration = max(getattr(s, "end", 0) for s in segments) or 1.0

    # RTF = processing time / audio duration
    rtf = transcription_time / audio_duration if audio_duration else float("inf")

    # Throughput: words per second (Whisper "tokens" are subword; words are comparable)
    full_text = " ".join(s.text for s in segments)
    word_count = len(full_text.split()) if full_text.strip() else 0
    words_per_sec = word_count / transcription_time if transcription_time > 0 else 0

    # Confidence: avg_logprob is negative; convert to 0-1 scale (e.g. exp(avg_logprob) or linear)
    logprobs = [getattr(s, "avg_logprob", None) for s in segments if getattr(s, "avg_logprob", None) is not None]
    if logprobs:
        import math
        avg_logprob = sum(logprobs) / len(logprobs)
        # exp(avg_logprob) gives a probability-like value in (0,1]
        avg_confidence = math.exp(avg_logprob) if avg_logprob <= 0 else 1.0
    else:
        avg_confidence = None

    mem_after_ram = get_memory_mb()
    mem_after_gpu = get_gpu_memory_mb() if device == "cuda" else None
    peak_ram_mb = max(mem_before_ram or 0, mem_after_ram or 0)
    peak_vram_mb = max(mem_before_gpu or 0, mem_after_gpu or 0) if device == "cuda" else None

    return {
        "audio_duration_sec": round(audio_duration, 2),
        "transcription_time_sec": round(transcription_time, 2),
        "rtf": round(rtf, 4),
        "words_per_sec": round(words_per_sec, 2),
        "word_count": word_count,
        "segment_count": len(segments),
        "avg_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
        "peak_ram_mb": round(peak_ram_mb, 2) if peak_ram_mb else None,
        "peak_vram_mb": round(peak_vram_mb, 2) if peak_vram_mb else None,
        "device": device,
        "compute_type": compute_type,
        "model_size": model_size,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python benchmark_transcribe.py <audio.wav | youtube_url>", file=sys.stderr)
        sys.exit(1)

    source = sys.argv[1].strip()
    model_size = os.getenv("ASR_MODEL", "small")
    device = os.getenv("ASR_DEVICE", "cuda").lower()
    compute = os.getenv("ASR_COMPUTE", "").strip() or ("int8_float16" if device == "cuda" else "int8")
    if device == "cpu":
        compute = os.getenv("ASR_COMPUTE", "int8")

    audio_path = source
    if source.startswith("http"):
        base = os.path.join(SCRIPT_DIR, f"bench_audio_{uuid.uuid4().hex[:8]}")
        print(f"Downloading audio from {source}...", file=sys.stderr, flush=True)
        audio_path = download_audio(source, base)
        if not audio_path:
            print("Download failed.", file=sys.stderr)
            sys.exit(1)
        try:
            result = run_benchmark(audio_path, device, compute, model_size)
            result["source"] = source
        finally:
            try:
                os.remove(audio_path)
            except Exception:
                pass
    else:
        if not os.path.exists(audio_path):
            print(f"File not found: {audio_path}", file=sys.stderr)
            sys.exit(1)
        result = run_benchmark(audio_path, device, compute, model_size)
        result["source"] = audio_path

    print("\n--- ASR Benchmark Results ---", file=sys.stderr)
    print(json.dumps(result, indent=2))
    print("\nRTF < 1.0 = faster than real-time.", file=sys.stderr)
    if result.get("rtf") is not None:
        print(f"RTF = {result['rtf']}", file=sys.stderr)


if __name__ == "__main__":
    main()
