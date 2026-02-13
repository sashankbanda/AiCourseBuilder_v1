import os
import sys
import uuid
import glob
from faster_whisper import WhisperModel
import yt_dlp
from tqdm import tqdm

MODEL_SIZE = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"

def download_audio(url, output_base):
    # output_base: e.g. "audio_1234"
    # We want "audio_1234.wav" as final
    # yt-dlp "outtmpl" can specify extension but postprocessor changes it.
    # Safe bet: let yt-dlp name it, we just control the base.
    
    output_template = f"{output_base}.%(ext)s"
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "quiet": False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # After download and conversion, expected file is output_base + ".wav"
    expected_path = f"{output_base}.wav"
    
    if os.path.exists(expected_path):
        return os.path.abspath(expected_path)
    
    # Fallback search
    files = glob.glob(f"{output_base}*.wav")
    if files:
        return os.path.abspath(files[0])
        
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <youtube_url>")
        sys.exit(1)

    youtube_url = sys.argv[1]
    unique_id = str(uuid.uuid4())[:8]
    base_filename = f"audio_{unique_id}"

    audio_path = None
    try:
        print(f"Downloading audio... (ID: {unique_id})")
        audio_path = download_audio(youtube_url, base_filename)
        
        if not audio_path or not os.path.exists(audio_path):
            print(f"Error: Audio file not found. Expected base: {base_filename}")
            sys.exit(1)
            
        print(f"Audio file ready: {audio_path}")
        print(f"File size: {os.path.getsize(audio_path) / (1024*1024):.2f} MB")

        print("Loading model on GPU...")
        model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE
        )

        print("Transcribing...")
        # faster_whisper returns a generator
        segments, info = model.transcribe(audio_path, beam_size=5, task="translate")
        
        print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")
        duration = info.duration
        print(f"Audio duration: {duration:.2f}s")

        full_text = []
        
        # Initialize tqdm
        # Use simple updates based on segment duration for smoothness
        with tqdm(total=round(duration, 2), unit="s", desc="Progress", 
                  bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]") as pbar:
            for segment in segments:
                full_text.append(segment.text)
                current_time = segment.end
                if current_time > pbar.n:
                    pbar.update(current_time - pbar.n)

        print("\n===TRANSCRIPT===")
        print(" ".join(full_text))

    except Exception as e:
        print(f"\nError occurred: {e}")
        # import traceback
        # traceback.print_exc()
        
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                # print(f"Cleaned up {audio_path}")
            except:
                pass

if __name__ == "__main__":
    main()
