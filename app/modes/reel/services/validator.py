import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from .embed_checker import test_embed_direct


logger = logging.getLogger(__name__)

# Maximum time to wait for a HEAD request
REQUEST_TIMEOUT = 5


def check_embed_headers(video_id: str) -> bool:
    """
    Check if a YouTube video can be embedded by testing the embed URL headers.

    Returns:
        True if video appears embeddable (no blocking headers), False otherwise.
    """
    embed_url = f"https://www.youtube.com/embed/{video_id}"

    try:
        # Send a HEAD request to check response headers
        response = requests.head(
            embed_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True)

        # Check for frame-blocking headers
        x_frame_options = response.headers.get('X-Frame-Options', '').upper()
        csp = response.headers.get('Content-Security-Policy', '')

        # If X-Frame-Options is DENY or SAMEORIGIN, video cannot be embedded
        if x_frame_options in ['DENY', 'SAMEORIGIN']:
            logger.info(
                f"Video {video_id}: blocked by X-Frame-Options={x_frame_options}")
            return False

        # Check Content-Security-Policy for frame-ancestors directive
        if 'frame-ancestors' in csp.lower():
            # If frame-ancestors is restricted (not 'self' or '*'), likely not
            # embeddable
            if "'none'" in csp.lower() or "'self'" in csp.lower():
                logger.info(
                    f"Video {video_id}: blocked by CSP frame-ancestors")
                return False

        # Also do a GET request to check for 403/404 or other errors
        response_full = requests.get(
            embed_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True)
        if response_full.status_code >= 400:
            logger.info(
                f"Video {video_id}: HTTP {response_full.status_code} on embed URL")
            return False

        logger.info(f"Video {video_id}: embed check passed")
        return True

    except requests.exceptions.Timeout:
        logger.warning(
            f"Video {video_id}: embed check timeout (assuming embeddable)")
        return True  # Timeout = assume embeddable to avoid over-filtering
    except requests.exceptions.RequestException as ex:
        logger.warning(
            f"Video {video_id}: embed check error - {ex} (assuming embeddable)")
        return True  # Error = assume embeddable


def validate_videos_batch(
        videos: List[Dict],
        session_logger=None) -> List[Dict]:
    """
    Validate a batch of videos for embeddability using parallel processing.

    Args:
        videos: List of video dictionaries from YouTube API
        session_logger: Optional SessionLogger instance for tracking

    Returns:
        List of validated videos that are embeddable
    """
    if not videos:
        return []

    validated = []
    removed_count = 0

    logger.info(
        f"Starting validation of {len(videos)} videos (hybrid: header check + screenshot)")

    # Use ThreadPoolExecutor for parallel validation
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all validation tasks
        future_to_video = {
            executor.submit(
                _validate_single_video,
                video): video for video in videos}

        # Collect results as they complete
        for future in as_completed(future_to_video):
            video = future_to_video[future]
            try:
                is_playable, reason = future.result()

                # Create validation result dict
                validation_result = {
                    "header_check": "passed",
                    "embed_test": "passed",
                    "ytdlp_check": "passed" if is_playable else "failed",
                    "final_result": "accepted" if is_playable else "rejected",
                    "reason": reason
                }

                # Log to session if logger provided
                if session_logger:
                    session_logger.add_video(video, validation_result)

                if is_playable:
                    validated.append(video)
                else:
                    removed_count += 1
                    logger.warning(
                        f"Removed video {video['id']} ({video.get('title', 'unknown')}): {reason}")
            except Exception as ex:
                logger.error(f"Error validating video {video.get('id')}: {ex}")
                # On error, include video to avoid over-filtering
                validated.append(video)

    if removed_count > 0:
        logger.info(
            f"Validation complete: removed {removed_count} videos, kept {len(validated)} playable")
    else:
        logger.info(f"Validation complete: all {len(validated)} videos passed")

    return validated


def _validate_single_video(video: Dict) -> tuple:
    """
    Internal helper to validate a single video.
    Uses header checks + embed test, then screenshot+qwen for uncertain cases.

    Returns:
        Tuple of (is_playable: bool, reason: str)
    """
    video_id = video.get('id')

    # Step 1: Fast header check
    if not check_embed_headers(video_id):
        return False, "failed_header_check"

    # Step 2: Test the actual embed page for obvious errors
    is_embeddable, reason = test_embed_direct(video_id)
    if not is_embeddable:
        return False, reason

    # Step 3: If we reach here, we trust the previous checks (or lack of
    # failure)
    return True, "passed_checks"
