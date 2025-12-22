from flask import render_template, request, session, redirect, url_for
from . import reel_bp
from .services.youtube_search import search_youtube_reels
from .services.validator import validate_videos_batch
from .services.logger import SessionLogger

# Store active session loggers (keyed by session ID) for Reel mode
active_sessions = {}

@reel_bp.route('/api/reels/search', methods=['POST'])
def search_reels():
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

@reel_bp.route('/api/reels/video-event', methods=['POST'])
def video_event():
    """Track video play/skip events."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        video_id = data.get('video_id')
        event_type = data.get('event_type')  # 'played', 'skipped', 'auto_skipped'
        
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
