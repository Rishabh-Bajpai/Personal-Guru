from flask import render_template, request
from . import reel_bp
from .services.youtube_search import search_youtube_reels
from .services.validator import validate_videos_batch
from .services.logger import SessionLogger

# Store active session loggers (keyed by session ID) for Reel mode
active_sessions = {}


@reel_bp.route('/<topic_name>')
def mode(topic_name):
    """Render the Reel mode interface."""
    return render_template('reel/mode.html', topic_name=topic_name)


@reel_bp.route('/api/search', methods=['POST'])
def search_reels():
    """
    Search for YouTube reels/shorts for a given topic.

    ---
    tags:
      - Reels
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - topic
          properties:
            topic:
              type: string
    responses:
      200:
        description: List of video results
        schema:
          type: object
          properties:
            reels:
              type: array
              items:
                type: object
            session_id:
              type: string
      400:
        description: Topic is required
    """
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()

        if not topic:
            return {"error": "Topic is required"}, 400

        # Create session logger
        session_logger = SessionLogger(topic)

        # Search for reels
        videos = search_youtube_reels(topic)

        # Validate videos (check if they're embeddable)
        validated_videos = validate_videos_batch(videos, session_logger)

        # Cap at 12 results for frontend
        validated_videos = validated_videos[:12]

        # Save session log
        session_logger.save()

        # Store session for event tracking
        active_sessions[session_logger.session_id] = session_logger

        return {
            'reels': validated_videos,
            'session_id': session_logger.session_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500


@reel_bp.route('/api/video-event', methods=['POST'])
def video_event():
    """
    Track video play/skip events.

    ---
    tags:
      - Reels
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - session_id
            - video_id
            - event_type
          properties:
            session_id:
              type: string
            video_id:
              type: string
            event_type:
              type: string
              enum: ['played', 'skipped', 'auto_skipped']
    responses:
      200:
        description: Event logged successfully
      400:
        description: Missing required fields
      404:
        description: Session not found
    """
    """Track video play/skip events."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        video_id = data.get('video_id')
        # 'played', 'skipped', 'auto_skipped'
        event_type = data.get('event_type')

        if not all([session_id, video_id, event_type]):
            return {"error": "Missing required fields"}, 400

        # Get session logger
        session_logger = active_sessions.get(session_id)
        if session_logger:
            session_logger.update_video_interaction(video_id, event_type)
            return {"status": "logged"}
        else:
            return {"error": "Session not found"}, 404

    except Exception as e:
        return {"error": str(e)}, 500
