"""
Test script for the transcriber: device check and optional full run.
Run from asr folder with venv active:

  python test_transcribe.py              # device + model check only
  python test_transcribe.py <youtube_url> # also run transcription and print result

For performance metrics (RTF, throughput, VRAM/RAM, confidence) use:
  python benchmark_transcribe.py <audio.wav | youtube_url>

Uses unbuffered output so you see progress in PowerShell.
"""
import os
import sys
import subprocess

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

# Ensure output is visible immediately
def log(msg: str, stream=sys.stderr) -> None:
    print(msg, file=stream, flush=True)


def test_device_and_model() -> bool:
    """Test GPU then CPU model load. Return True if at least one works."""
    log("--- Testing device and model ---")
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        log(f"ERROR: faster_whisper not installed: {e}")
        return False

    model_size = "tiny"
    gpu_ok = False
    cpu_ok = False

    log("Testing GPU (CUDA)...")
    try:
        m = WhisperModel(model_size, device="cuda", compute_type="float16")
        del m
        gpu_ok = True
        log("  GPU: OK")
    except Exception as e:
        log(f"  GPU: failed - {e}")

    log("Testing CPU...")
    try:
        m = WhisperModel(model_size, device="cpu", compute_type="int8")
        del m
        cpu_ok = True
        log("  CPU: OK")
    except Exception as e:
        log(f"  CPU: failed - {e}")

    if not gpu_ok and not cpu_ok:
        log("ERROR: Neither GPU nor CPU model load succeeded.")
        return False
    log("--- Device test done ---")
    return True


def run_transcribe(url: str) -> None:
    """Run transcribe.py on URL and print transcript preview."""
    log(f"--- Running transcribe.py on URL ---")
    log(f"URL: {url}")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # transcribe.py is in the parent directory of tests/
    parent_dir = os.path.dirname(script_dir)
    script = os.path.join(parent_dir, "transcribe.py")
    if not os.path.exists(script):
        log(f"ERROR: transcribe.py not found at {script}")
        return

    try:
        result = subprocess.run(
            [sys.executable, script, url],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=parent_dir,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired:
        log("ERROR: transcribe.py timed out (10 min)")
        return

    log(f"Exit code: {result.returncode}")
    if result.stderr:
        log("stderr (preview):")
        log(result.stderr[:2000])

    if result.returncode != 0:
        log("Transcription failed (non-zero exit).")
        return

    marker = "===TRANSCRIPT==="
    idx = result.stdout.find(marker)
    if idx == -1:
        log("No ===TRANSCRIPT=== in stdout. Full stdout (first 1500 chars):")
        log(result.stdout[:1500], sys.stdout)
        return

    transcript = result.stdout[idx + len(marker) :].strip()
    log(f"Transcript length: {len(transcript)} chars")
    preview = transcript[:400] + "..." if len(transcript) > 400 else transcript
    log("Preview:", sys.stdout)
    print(preview, flush=True)
    log("--- Done ---")


def main() -> None:
    log("Transcriber test")
    log("================")

    if not test_device_and_model():
        sys.exit(1)

    if len(sys.argv) > 1:
        run_transcribe(sys.argv[1])
    else:
        log("")
        log("To test full pipeline, run:")
        log('  python test_transcribe.py "https://www.youtube.com/watch?v=SHORT_VIDEO_ID"')
        log("(Use a short clip so the test finishes quickly.)")


if __name__ == "__main__":
    main()
