from youtubesearchpython import VideosSearch
from youtube_transcript_api import YouTubeTranscriptApi
import os

async def search_videos(query: str, max_results: int = 1):
    try:
        videos_search = VideosSearch(query, limit=max_results)
        results = videos_search.result()
        
        # Normalize to match expected format
        videos = []
        for item in results['result']:
            videos.append({
                "id": {"videoId": item['id']},
                "snippet": {
                    "title": item['title'],
                    "thumbnails": {"high": {"url": item['thumbnails'][0]['url']}},
                    "channelTitle": item['channel']['name']
                }
            })
        return videos
    except Exception as e:
        print(f"YouTube Search Error: {e}")
        return []

async def get_video_metadata(video_id: str):
    # youtube-search-python doesn't have a direct "get details by ID" that is as rich as the API
    # but we can search by ID or use the URL. 
    # Alternatively, since we have the API Key, we COULD use google-api-python-client
    # asking for the ID in VideosSearch works too.
    try:
        videos_search = VideosSearch(video_id, limit=1)
        results = videos_search.result()
        if results['result']:
            item = results['result'][0]
            # Normalize to match partially what the TS sent (which was raw YouTube API obj)
            return {
                "id": item['id'],
                "snippet": {
                    "title": item['title'],
                    "description": item.get('descriptionSnippet', [{}])[0].get('text', ''),
                    "thumbnails": {"high": {"url": item['thumbnails'][0]['url']}},
                },
                "contentDetails": {
                    "duration": item['duration']
                }
            }
        return None
    except Exception as e:
        print(f"YouTube Metadata Error: {e}")
        return None

async def get_transcript(video_id: str):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine text
        full_text = " ".join([t['text'] for t in transcript_list])
        return full_text
    except Exception as e:
        # print(f"Transcript Error: {e}")
        return None

import yt_dlp
import uuid
import tempfile

def download_audio(url: str) -> str:
    # return path to audio file
    temp_dir = tempfile.gettempdir()
    unique_id = str(uuid.uuid4())[:8]
    output_base = os.path.join(temp_dir, f"audio_{unique_id}")
    output_template = f"{output_base}.%(ext)s"
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
        "quiet": True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        expected_path = f"{output_base}.mp3"
        if os.path.exists(expected_path):
            return expected_path
        return None
    except Exception as e:
        print(f"Download Error: {e}")
        return None

