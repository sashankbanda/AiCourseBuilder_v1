import os
import uuid
import tempfile
import asyncio
from faster_whisper import WhisperModel
import yt_dlp
from typing import Optional

MODEL_SIZE = "medium"
DEVICE = "cuda" if os.environ.get("UseCUDA", "false").lower() == "true" else "cpu"
# Or just let faster-whisper detect if cuda is available?
# Better:
import torch
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

def download_audio(url: str, output_base: str) -> Optional[str]:
    output_template = f"{output_base}.%(ext)s"
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "quiet": True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        expected_path = f"{output_base}.wav"
        if os.path.exists(expected_path):
            return os.path.abspath(expected_path)
            
        import glob
        files = glob.glob(f"{output_base}*.wav")
        if files:
            return os.path.abspath(files[0])
            
        return None
    except Exception as e:
        print(f"Download Error: {e}")
        return None

async def transcribe_with_asr(youtube_url: str) -> str:
    # Use a thread executor for blocking tasks (download + transcribe)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, youtube_url)

def _transcribe_sync(youtube_url: str) -> str:
    temp_dir = tempfile.mkdtemp()
    unique_id = str(uuid.uuid4())[:8]
    base_filename = os.path.join(temp_dir, f"audio_{unique_id}")
    audio_path = None
    
    try:
        print(f"ASR Service: Downloading {youtube_url}...")
        audio_path = download_audio(youtube_url, base_filename)
        
        if not audio_path:
            raise Exception("Failed to download audio")

        print(f"ASR Service: Loading Whisper model ({DEVICE})...")
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        
        print(f"ASR Service: Transcribing...")
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        full_text = []
        for segment in segments:
            full_text.append(segment.text)
            
        return " ".join(full_text)
        
    except Exception as e:
        print(f"ASR Service Error: {e}")
        raise e
    finally:
        # Cleanup
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
        try:
            os.rmdir(temp_dir)
        except:
            pass
