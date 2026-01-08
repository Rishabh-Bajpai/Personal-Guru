"""
Server-side exceptions (5xx HTTP status codes).

These represent errors caused by system issues, not user input.
"""

from typing import Optional
from .base import PersonalGuruException


# ============================================================================
# SERVER-SIDE ERRORS (5xx) - System / Service Issues
# ============================================================================

class ServerError(PersonalGuruException):
    """Base class for all server-side errors (5xx)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('log_category', 'SERVER_ERROR')
        kwargs.setdefault('http_status', 500)
        kwargs.setdefault(
            'user_message',
            'We encountered a technical problem. Please try again later.')
        super().__init__(message, **kwargs)


# ============================================================================
# Database Errors (500)
# ============================================================================

class DatabaseError(ServerError):
    """Database operation error (500)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'DB500')
        kwargs.setdefault(
            'user_message',
            'We are experiencing database issues. Please try again shortly.')
        kwargs.setdefault('should_retry', True)
        super().__init__(message, **kwargs)


class DatabaseConnectionError(DatabaseError):
    """Cannot connect to database."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'DB001')
        super().__init__(message, **kwargs)


class DatabaseOperationError(DatabaseError):
    """Database query or operation failed."""

    def __init__(
            self,
            message: str,
            operation: Optional[str] = None,
            **kwargs):
        kwargs.setdefault('error_code', 'DB002')
        if operation:
            kwargs['debug_info'] = kwargs.get('debug_info', {})
            kwargs['debug_info']['operation'] = operation
        super().__init__(message, **kwargs)


class DatabaseIntegrityError(DatabaseError):
    """Database constraint violation."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'DB003')
        kwargs.setdefault(
            'user_message',
            'This action would violate data integrity. Please check your input.')
        super().__init__(message, **kwargs)


# ============================================================================
# External Service Errors (503)
# ============================================================================

class ExternalServiceError(ServerError):
    """External service unavailable (503)."""

    def __init__(self, message: str, service: Optional[str] = None, **kwargs):
        kwargs.setdefault('error_code', 'EXT503')
        kwargs.setdefault('http_status', 503)
        kwargs.setdefault(
            'user_message',
            'An external service is temporarily unavailable. Please try again in a moment.')
        kwargs.setdefault('should_retry', True)
        if service:
            kwargs['debug_info'] = kwargs.get('debug_info', {})
            kwargs['debug_info']['service'] = service
        super().__init__(message, **kwargs)


# ============================================================================
# LLM/AI Service Errors (503)
# ============================================================================

class LLMError(ExternalServiceError):
    """LLM/AI service error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'LLM503')
        kwargs.setdefault(
            'user_message',
            'Our AI service is temporarily unavailable. Please try again in a moment.')
        super().__init__(message, service='LLM', **kwargs)


class LLMConnectionError(LLMError):
    """Cannot connect to LLM service."""

    def __init__(self, message: str, endpoint: Optional[str] = None, **kwargs):
        kwargs.setdefault('error_code', 'LLM001')
        if endpoint:
            kwargs['debug_info'] = kwargs.get('debug_info', {})
            kwargs['debug_info']['endpoint'] = endpoint
        super().__init__(message, **kwargs)


class LLMResponseError(LLMError):
    """Invalid or unexpected LLM response."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'LLM002')
        kwargs.setdefault(
            'user_message',
            'The AI service returned an unexpected response. Please try again.')
        super().__init__(message, **kwargs)


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, message: str, timeout: Optional[int] = None, **kwargs):
        kwargs.setdefault('error_code', 'LLM003')
        kwargs.setdefault(
            'user_message',
            'The AI service is taking too long to respond. Please try again.')
        if timeout:
            kwargs['debug_info'] = kwargs.get('debug_info', {})
            kwargs['debug_info']['timeout_seconds'] = timeout
        super().__init__(message, **kwargs)


# ============================================================================
# TTS/STT Service Errors (503)
# ============================================================================

class TTSError(ExternalServiceError):
    """Text-to-Speech service error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'TTS503')
        kwargs.setdefault(
            'user_message',
            'Audio generation is temporarily unavailable. Please try again later.')
        super().__init__(message, service='TTS', **kwargs)


class STTError(ExternalServiceError):
    """Speech-to-Text service error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'STT503')
        kwargs.setdefault(
            'user_message',
            'Audio transcription is temporarily unavailable. Please try again later.')
        super().__init__(message, service='STT', **kwargs)


# ============================================================================
# Configuration Errors (500)
# ============================================================================

class ConfigurationError(ServerError):
    """Configuration error (500)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('error_code', 'CFG500')
        kwargs.setdefault('log_category', 'CRITICAL')
        kwargs.setdefault(
            'user_message',
            'System configuration error. Please contact support.')
        super().__init__(message, **kwargs)


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    def __init__(
            self,
            message: str,
            missing_vars: Optional[list] = None,
            **kwargs):
        kwargs.setdefault('error_code', 'CFG001')
        if missing_vars:
            kwargs['debug_info'] = kwargs.get('debug_info', {})
            kwargs['debug_info']['missing_vars'] = missing_vars
        super().__init__(message, **kwargs)
