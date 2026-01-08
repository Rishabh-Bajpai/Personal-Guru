import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import logging

load_dotenv()

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Configure simple logging for skipped-video diagnostics
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def search_youtube_reels(topic, max_results=12):
    """
    Search YouTube for reels matching the given topic.
    Fetches multiple pages if needed to collect the desired number of videos.

    Filtering is minimal: only excludes private videos.
    Frontend handles non-embeddable videos with automatic YouTube redirect.

    Args:
        topic: Search query/topic
        max_results: Maximum number of results to return (default: 12)

    Returns:
        List of reel data dictionaries containing title, url, thumbnail, etc.
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY not found in .env file")

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        reels = []
        skipped_count = 0
        next_page_token = None
        attempts = 0

        # Keep fetching pages until we collect `max_results` reels or run out of pages
        # "Fetch significantly more videos since ~80%+ won't be actually embeddable"--> not true anymore
        # "YouTube API embeddable flag is unreliable, will be caught by VLM validation"--> not true anymore
        # Fetch +2 to account for filtering
        target_fetch = max(int(max_results + 2), 12)

        while len(reels) < target_fetch and attempts < 10:
            attempts += 1
            per_page = min(50, target_fetch - len(reels))
            # Ensure query targets shorts by appending #shorts if not present
            query = topic
            if "#shorts" not in query.lower():
                # append #shorts to query for vertical videos and remove it for
                # any video with duration < 4 minutes
                query = f"{query} #shorts"

            search_call = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                videoDuration='short',
                maxResults=per_page,
                order='relevance',
                regionCode='US',
                relevanceLanguage='en',
                pageToken=next_page_token
            )

            search_response = search_call.execute()
            items = search_response.get('items', [])
            if not items:
                break

            # Batch status lookup for privacy check only
            video_ids = [
                it.get(
                    'id',
                    {}).get('videoId') for it in items if it.get(
                    'id',
                    {}).get('videoId')]
            video_ids = [v for v in video_ids if v]

            status_map = {}
            if video_ids:
                try:
                    # Check privacy status and embeddable flag
                    status_response = youtube.videos().list(
                        part='status',
                        id=','.join(video_ids)
                    ).execute()

                    for st_item in status_response.get('items', []):
                        vid = st_item.get('id')
                        status_obj = st_item.get('status', {}) or {}
                        status_map[vid] = {
                            'privacyStatus': status_obj.get('privacyStatus'),
                            # Default to True if not specified
                            'embeddable': status_obj.get('embeddable', True)
                        }
                except Exception as ex:
                    logger.info(f"Failed to retrieve video status: {ex}")
                    status_map = {
                        vid: {
                            'privacyStatus': 'public',
                            'embeddable': True} for vid in video_ids}

            for item in items:
                if len(reels) >= target_fetch:
                    break

                video_id = item.get('id', {}).get('videoId')
                if not video_id:
                    continue

                # Only skip private videos AND non-embeddable videos
                st = status_map.get(video_id)
                if st and st.get('privacyStatus') == 'private':
                    skipped_count += 1
                    logger.info(f"Skipping video {video_id}: private")
                    continue

                # Also skip videos where embedding is disabled
                if st and st.get('embeddable') is False:
                    skipped_count += 1
                    logger.info(f"Skipping video {video_id}: not embeddable")
                    continue

                snippet = item.get('snippet', {})
                title = snippet.get('title', '')
                thumbnail = snippet.get(
                    'thumbnails',
                    {}).get(
                    'medium',
                    {}).get('url') or snippet.get(
                    'thumbnails',
                    {}).get(
                    'default',
                    {}).get('url') or ''

                reel_data = {
                    'id': video_id,
                    'title': title,
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'thumbnail': thumbnail,
                    'channel': snippet.get('channelTitle', '')
                }
                reels.append(reel_data)

            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break

        logger.info(
            f"Search '{topic}': fetched {len(reels)} videos (will filter via VLM to find embeddable ones), skipped {skipped_count} private videos")
        return reels
    except Exception as e:
        raise Exception(f"YouTube API error: {str(e)}")
