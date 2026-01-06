"""
Base exception class for Personal-Guru application.
"""

import logging
from typing import Optional, Dict, Any
from flask import session


class PersonalGuruException(Exception):
    """
    Base exception for all Personal-Guru application errors.

    Attributes:
        error_code: Unique identifier for tracking (e.g., "VAL010", "DB500", "LLM503")
        user_message: Clear, actionable message for end users
        debug_info: Dictionary with additional context for debugging
        http_status: HTTP status code (400, 401, 403, 404, 500, 503, etc.)
        log_category: "CLIENT_ERROR" (4xx) or "SERVER_ERROR" (5xx) or "CRITICAL"
        should_retry: Whether the operation can be retried
    """

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN",
        user_message: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
        http_status: int = 500,
        log_category: str = "SERVER_ERROR",
        should_retry: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.user_message = user_message or "An unexpected error occurred. Please try again."
        self.debug_info = debug_info or {}
        self.http_status = http_status
        self.log_category = log_category
        self.should_retry = should_retry

    def log(self, logger: logging.Logger, endpoint: str = ""):
        """
        Log this exception with structured format.

        Args:
            logger: Logger instance to use
            endpoint: Current endpoint/route where error occurred
        """
        # Get session ID for tracking (never log username)
        session_id = session.get(
            '_id', 'no_session') if session else 'no_session'

        log_message = (
            f"[{self.log_category}] [{self.error_code}] {self.__class__.__name__}: {self.message}\n"
            f"  User Message: \"{self.user_message}\"\n"
            f"  Session: {session_id}\n"
            f"  Endpoint: {endpoint}\n"
            f"  Debug: {self.debug_info}")

        # Choose log level based on category
        if self.log_category == "CRITICAL":
            logger.critical(log_message, exc_info=True)
        elif self.log_category == "SERVER_ERROR":
            logger.error(log_message, exc_info=True)
        else:  # CLIENT_ERROR
            logger.warning(log_message, exc_info=False)
