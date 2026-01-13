"""
Client-side exceptions (4xx HTTP status codes).

These represent errors caused by user input or client requests.
"""

from typing import Optional
from .base import PersonalGuruException


# ============================================================================
# CLIENT-SIDE ERRORS (4xx) - User Input / Request Issues
# ============================================================================


class ClientError(PersonalGuruException):
    """Base class for all client-side errors (4xx)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("log_category", "CLIENT_ERROR")
        kwargs.setdefault("http_status", 400)
        super().__init__(message, **kwargs)


# ============================================================================
# Validation Errors (400)
# ============================================================================


class ValidationError(ClientError):
    """Base validation error (400 - Bad Request)."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        kwargs.setdefault("error_code", "VAL400")
        kwargs.setdefault("user_message", "Please check your input and try again.")
        if field:
            kwargs["debug_info"] = kwargs.get("debug_info", {})
            kwargs["debug_info"]["field"] = field
        super().__init__(message, **kwargs)


class ModelValidationError(ValidationError):
    """Database model validation error."""

    def __init__(self, message: str, model: Optional[str] = None, **kwargs):
        kwargs.setdefault("error_code", "VAL001")
        if model:
            kwargs["debug_info"] = kwargs.get("debug_info", {})
            kwargs["debug_info"]["model"] = model
        super().__init__(message, **kwargs)


class InputValidationError(ValidationError):
    """User input validation error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("error_code", "VAL002")
        super().__init__(message, **kwargs)


class QuizValidationError(ValidationError):
    """Quiz structure validation error."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("error_code", "VAL003")
        kwargs.setdefault(
            "user_message",
            "The quiz data is invalid. Please try generating a new quiz.",
        )
        super().__init__(message, **kwargs)


# ============================================================================
# Authentication Errors (401)
# ============================================================================


class AuthenticationError(ClientError):
    """Authentication error (401 - Unauthorized)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("error_code", "AUTH401")
        kwargs.setdefault("http_status", 401)
        kwargs.setdefault("user_message", "Please log in to continue.")
        super().__init__(message, **kwargs)


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""

    def __init__(self, message: str = "Invalid username or password", **kwargs):
        kwargs.setdefault("error_code", "AUTH001")
        kwargs.setdefault(
            "user_message", "Invalid username or password. Please try again."
        )
        super().__init__(message, **kwargs)


class SessionExpiredError(AuthenticationError):
    """Session has expired."""

    def __init__(self, message: str = "Your session has expired", **kwargs):
        kwargs.setdefault("error_code", "AUTH002")
        kwargs.setdefault(
            "user_message", "Your session has expired. Please log in again."
        )
        super().__init__(message, **kwargs)


# ============================================================================
# Authorization Errors (403)
# ============================================================================


class AuthorizationError(ClientError):
    """Authorization error (403 - Forbidden)."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("error_code", "AUTHZ403")
        kwargs.setdefault("http_status", 403)
        kwargs.setdefault(
            "user_message", "You do not have permission to perform this action."
        )
        super().__init__(message, **kwargs)


class AccessDeniedError(AuthorizationError):
    """User lacks permission to access resource."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("error_code", "AUTHZ001")
        super().__init__(message, **kwargs)


# ============================================================================
# Resource Not Found Errors (404)
# ============================================================================


class ResourceNotFoundError(ClientError):
    """Resource not found (404)."""

    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        kwargs.setdefault("error_code", "RES404")
        kwargs.setdefault("http_status", 404)
        kwargs.setdefault("user_message", "The requested item was not found.")
        if resource_type:
            kwargs["debug_info"] = kwargs.get("debug_info", {})
            kwargs["debug_info"]["resource_type"] = resource_type
        super().__init__(message, **kwargs)


class TopicNotFoundError(ResourceNotFoundError):
    """Topic does not exist."""

    def __init__(self, topic_name: str, **kwargs):
        kwargs.setdefault("error_code", "RES001")
        kwargs.setdefault("user_message", f'Topic "{topic_name}" was not found.')
        kwargs["debug_info"] = kwargs.get("debug_info", {})
        kwargs["debug_info"]["topic_name"] = topic_name
        super().__init__(
            f"Topic '{topic_name}' not found", resource_type="topic", **kwargs
        )


class UserNotFoundError(ResourceNotFoundError):
    """User does not exist."""

    def __init__(self, message: str = "User not found", **kwargs):
        kwargs.setdefault("error_code", "RES002")
        kwargs.setdefault("user_message", "User not found.")
        super().__init__(message, resource_type="user", **kwargs)
