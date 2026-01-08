"""
Session logging module for tracking video searches and user interactions.
Creates timestamped log files for each search session.
"""
import json
import os
from datetime import datetime
from typing import Dict, Any


class SessionLogger:
    """Manages logging for a single search session."""

    def __init__(self, search_query: str):
        """
        Initialize a new session logger.

        Args:
            search_query: The search term used
        """
        self.search_query = search_query
        self.timestamp = datetime.now()
        self.session_id = self.timestamp.strftime("%Y-%m-%d_%H-%M-%S")

        # Create logs directory structure
        self.base_dir = "logs"
        self.session_dir = os.path.join(self.base_dir, self.session_id)
        os.makedirs(self.session_dir, exist_ok=True)

        # Session data
        self.data = {
            "session_id": self.session_id,
            "search_query": search_query,
            "timestamp": self.timestamp.isoformat(),
            "total_videos_found": 0,
            "videos": [],
            "summary": {
                "accepted_videos": 0,
                "rejected_videos": 0,
                "videos_played": 0,
                "videos_skipped": 0
            }
        }

    def add_video(self, video_data: Dict[str, Any],
                  validation_results: Dict[str, Any] = None):
        """
        Add a video to the session log.

        Args:
            video_data: Video metadata (id, title, channel, url, etc.)
            validation_results: Results of validation tests
        """
        video_entry = {
            "id": video_data.get("id"),
            "title": video_data.get("title"),
            "channel": video_data.get("channel"),
            "url": video_data.get("url"),
            "thumbnail": video_data.get("thumbnail"),
            "validation": validation_results or {},
            "user_interaction": {
                "played": False,
                "skipped": False,
                "auto_skipped": False,
                "timestamp": None
            }
        }

        self.data["videos"].append(video_entry)
        self.data["total_videos_found"] = len(self.data["videos"])

        # Update summary
        if validation_results and validation_results.get(
                "final_result") == "accepted":
            self.data["summary"]["accepted_videos"] += 1
        elif validation_results and validation_results.get("final_result") == "rejected":
            self.data["summary"]["rejected_videos"] += 1

    def update_video_interaction(self, video_id: str, event_type: str):
        """
        Update user interaction for a video.

        Args:
            video_id: YouTube video ID
            event_type: Type of interaction ('played', 'skipped', 'auto_skipped')
        """
        for video in self.data["videos"]:
            if video["id"] == video_id:
                video["user_interaction"][event_type] = True
                video["user_interaction"]["timestamp"] = datetime.now().isoformat()

                # Update summary
                if event_type == "played":
                    self.data["summary"]["videos_played"] += 1
                elif event_type in ["skipped", "auto_skipped"]:
                    self.data["summary"]["videos_skipped"] += 1

                # Auto-save after each interaction
                self.save()
                break

    def save(self):
        """Save the session log to disk."""
        log_file = os.path.join(self.session_dir, "session.json")
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_log_path(self) -> str:
        """Get the path to the session log file."""
        return os.path.join(self.session_dir, "session.json")
