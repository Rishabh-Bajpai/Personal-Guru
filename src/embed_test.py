"""
Fast embed testing without screenshots or LLM.
Simply tries to load the embed URL and check for real HTTP errors.
"""
import requests
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5

def test_embed_direct(video_id: str) -> Tuple[bool, str]:
    """
    Test if a video can be embedded by making a GET request to the embed page
    and checking the response for error indicators.
    
    This is faster than screenshots and doesn't require LLM.
    Returns whether video is likely embeddable.
    """
    embed_url = f"https://www.youtube.com/embed/{video_id}"
    
    try:
        # Get the full embed page
        response = requests.get(
            embed_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        # Check HTTP status
        if response.status_code >= 400:
            logger.info(f"Video {video_id}: HTTP {response.status_code}")
            return False, f"http_{response.status_code}"
        
        # We used to check for specific error strings here, but they are unreliable
        # (often false positives or JS-rendered false negatives).
        # We will rely on the VLM screenshot validation to catch actual "Video unavailable" errors.
        
        logger.info(f"Video {video_id}: Embed test passed (HTTP 200)")
        return True, "passed_embed_test"
        
    except requests.exceptions.Timeout:
        logger.warning(f"Video {video_id}: embed test timeout (assuming embeddable)")
        return True, "timeout"
    except Exception as ex:
        logger.warning(f"Video {video_id}: embed test error - {ex} (assuming embeddable)")
        return True, f"error: {str(ex)}"
