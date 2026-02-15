"""
Transcribe YouTube video audio using faster-whisper (GPU preferred, CPU fallback).
Output: prints ===TRANSCRIPT=== then the full text so the backend can parse it.
Also writes transcript to asr/transcript_output.txt so you always have the result.
"""
import os
import sys
import uuid
import glob

# Force unbuffered output immediately so PowerShell/terminal shows everything
class _Unbuffered:
    def __init__(self, stream):
        self._stream = stream
    def write(self, data):
        self._stream.write(data)
        self._stream.flush()
    def writable(self):
        return True
    def __getattr__(self, name):
        return getattr(self._stream, name)
sys.stdout = _Unbuffered(sys.stdout)
sys.stderr = _Unbuffered(sys.stderr)

from faster_whisper import WhisperModel
import yt_dlp
import tqdm

# Where to save transcript so you can always open it (even if terminal doesn't show output)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPT_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "transcript_output.txt")

MODEL_SIZE = os.getenv("ASR_MODEL", "small")

# Default CPU to avoid GPU driver crash (exit 0xC0000409) during long transcription on some systems.
# Set ASR_DEVICE=cuda to use GPU; script will fall back to CPU if GPU fails at load time.
ASR_DEVICE = os.getenv("ASR_DEVICE", "cpu").lower()
ASR_COMPUTE_ENV = os.getenv("ASR_COMPUTE", "float16")


def _log(msg: str, use_stderr: bool = True) -> None:
    """Print and flush so output is visible immediately (no buffering)."""
    stream = sys.stderr if use_stderr else sys.stdout
    print(msg, file=stream, flush=True)


def download_audio(url: str, output_base: str):
    output_template = f"{output_base}.%(ext)s"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    expected_path = f"{output_base}.wav"
    if os.path.exists(expected_path):
        return os.path.abspath(expected_path)
    files = glob.glob(f"{output_base}*.wav")
    if files:
        return os.path.abspath(files[0])
    return None


def _run_transcription(audio_path: str, device: str, compute_type: str) -> str:
    _log(f"Loading model on {device.upper()} with compute_type={compute_type}...")
    model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute_type)

    _log("Transcribing...")
    segments, info = model.transcribe(audio_path, beam_size=5, task="translate")

    _log(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")
    duration = info.duration
    _log(f"Audio duration: {duration:.2f}s")

    full_text = []
    try:
        # Progress by segment count so we don't depend on duration/timing
        with tqdm.tqdm(desc="Progress", unit=" seg", file=sys.stderr, dynamic_ncols=True) as pbar:
            for segment in segments:
                full_text.append(segment.text)
                pbar.update(1)
    except Exception as e:
        _log(f"Transcription loop error after {len(full_text)} segments: {e}")
        raise RuntimeError(f"Transcription failed: {e}") from e

    return " ".join(full_text)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <youtube_url>")
        sys.exit(1)

    _log(f"Transcript will be saved to: {TRANSCRIPT_OUTPUT_FILE}")

    youtube_url = sys.argv[1]
    unique_id = str(uuid.uuid4())[:8]
    base_filename = f"audio_{unique_id}"
    audio_path = None

    try:
        _log(f"Downloading audio... (ID: {unique_id})")
        audio_path = download_audio(youtube_url, base_filename)
        if not audio_path or not os.path.exists(audio_path):
            _log(f"Error: Audio file not found. Expected base: {base_filename}")
            sys.exit(1)
        _log(f"Audio file ready: {audio_path}")
        _log(f"File size: {os.path.getsize(audio_path) / (1024 * 1024):.2f} MB")

        if ASR_DEVICE == "cpu":
            transcript_text = _run_transcription(audio_path, "cpu", os.getenv("ASR_COMPUTE", "int8"))
        else:
            try:
                transcript_text = _run_transcription(audio_path, "cuda", ASR_COMPUTE_ENV)
            except Exception as gpu_err:
                _log(f"GPU failed ({gpu_err}), falling back to CPU.")
                transcript_text = _run_transcription(audio_path, "cpu", "int8")

        # Backend parses everything after this marker
        print("\n===TRANSCRIPT===")
        print(transcript_text)

        # Always write to file so you can open it even if terminal doesn't show output
        with open(TRANSCRIPT_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        _log(f"Saved transcript to: {TRANSCRIPT_OUTPUT_FILE}")

    except Exception as e:
        _log(f"Error occurred: {e}")
        sys.exit(1)
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
