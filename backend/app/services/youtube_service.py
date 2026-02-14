from youtubesearchpython import VideosSearch


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
    try:
        videos_search = VideosSearch(video_id, limit=1)
        results = videos_search.result()
        if results['result']:
            item = results['result'][0]
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


