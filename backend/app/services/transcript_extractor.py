"""
Transcript Extractor Service for AiCourseBuilder.

Ported from: https://github.com/sashankbanda/yt_transcript_extractor

Two-tier extraction:
  1. Official YouTube captions (auto-selects English or first available)
  2. Whisper speech-to-text fallback (faster-whisper, CPU, int8)

Usage (within the app):
    transcript = await extract_transcript(video_id)
"""

import os
import asyncio
import tempfile
import logging
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whisper model (lazy-loaded singleton)
# ---------------------------------------------------------------------------
_whisper_model: Optional[WhisperModel] = None
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")


def _get_whisper_model() -> WhisperModel:
    """Lazy-load the Whisper model once."""
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model: %s (first-time download may take a moment)", WHISPER_MODEL_SIZE)
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully")
    return _whisper_model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_transcript(video_id: str) -> str:
    """
    Extract transcript for a YouTube video.
    
    Tries official captions first, falls back to Whisper transcription.
    Returns the full transcript text (never None — raises on total failure).
    """
    logger.info("Extracting transcript for video: %s", video_id)

    # Step 1: Try official captions
    transcript = _get_official_captions(video_id)
    if transcript:
        logger.info("Official captions found for %s (%d chars)", video_id, len(transcript))
        return transcript

    # Step 2: Fallback to Whisper
    logger.warning("No captions for %s — falling back to Whisper transcription", video_id)
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # Run blocking Whisper work in a thread executor
    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(None, _transcribe_via_whisper, youtube_url)

    if not transcript:
        raise RuntimeError(f"Failed to extract transcript for video {video_id}")

    logger.info("Whisper transcription complete for %s (%d chars)", video_id, len(transcript))
    return transcript


# ---------------------------------------------------------------------------
# Caption extraction
# ---------------------------------------------------------------------------

def _get_official_captions(video_id: str) -> Optional[str]:
    """Fetch official captions. Auto-selects English or first available language."""
    try:
        logger.info("Attempting official captions for %s...", video_id)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        available = list(transcript_list)
        if not available:
            logger.warning("No transcripts available")
            return None

        for t in available:
            tag = "(auto-generated)" if t.is_generated else "(manual)"
            logger.debug("  Available: %s [%s] %s", t.language, t.language_code, tag)

        # Priority: English manual → English auto → first available
        selected = None

        for t in available:
            if t.language_code.startswith("en") and not t.is_generated:
                selected = t
                break
        if not selected:
            for t in available:
                if t.language_code.startswith("en"):
                    selected = t
                    break
        if not selected:
            selected = available[0]

        logger.info("Using transcript: %s [%s]", selected.language, selected.language_code)
        transcript_data = selected.fetch()
        return " ".join(entry["text"] for entry in transcript_data)

    except Exception as e:
        logger.warning("Caption extraction failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Whisper fallback
# ---------------------------------------------------------------------------

def _download_audio(youtube_url: str) -> str:
    """Download audio from YouTube as MP3. Returns path to the file."""
    logger.info("Downloading audio via yt-dlp...")
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "audio.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    audio_path = os.path.join(temp_dir, "audio.mp3")
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio file was not created after download")

    logger.info("Audio downloaded to: %s", audio_path)
    return audio_path


def _transcribe_via_whisper(youtube_url: str) -> str:
    """Download audio and transcribe with Whisper. Cleans up temp files."""
    audio_path = None
    try:
        audio_path = _download_audio(youtube_url)

        logger.info("Starting Whisper transcription...")
        model = _get_whisper_model()
        segments, info = model.transcribe(audio_path)
        logger.info("Detected language: %s", info.language)

        transcript_text = " ".join(segment.text for segment in segments).strip()
        logger.info("Transcription completed (%d chars)", len(transcript_text))
        return transcript_text

    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
        return ""
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                os.rmdir(os.path.dirname(audio_path))
            except OSError:
                pass
