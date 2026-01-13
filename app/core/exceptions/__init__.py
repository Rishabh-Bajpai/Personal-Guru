"""
Personal-Guru Exception Hierarchy.

Organized into:
- base.py: Base PersonalGuruException class
- client_errors.py: 4xx errors (user/client issues)
- server_errors.py: 5xx errors (system/server issues)
"""

# Base exception
from .base import PersonalGuruException

# Client-side errors (4xx)
from .client_errors import (
    ClientError,
    ValidationError,
    ModelValidationError,
    InputValidationError,
    QuizValidationError,
    AuthenticationError,
    InvalidCredentialsError,
    SessionExpiredError,
    AuthorizationError,
    AccessDeniedError,
    ResourceNotFoundError,
    TopicNotFoundError,
    UserNotFoundError,
)

# Server-side errors (5xx)
from .server_errors import (
    ServerError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseOperationError,
    DatabaseIntegrityError,
    ExternalServiceError,
    LLMError,
    LLMConnectionError,
    LLMResponseError,
    LLMTimeoutError,
    TTSError,
    STTError,
    ConfigurationError,
    MissingConfigError,
)

__all__ = [
    # Base
    "PersonalGuruException",
    # Client errors (4xx)
    "ClientError",
    "ValidationError",
    "ModelValidationError",
    "InputValidationError",
    "QuizValidationError",
    "AuthenticationError",
    "InvalidCredentialsError",
    "SessionExpiredError",
    "AuthorizationError",
    "AccessDeniedError",
    "ResourceNotFoundError",
    "TopicNotFoundError",
    "UserNotFoundError",
    # Server errors (5xx)
    "ServerError",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseOperationError",
    "DatabaseIntegrityError",
    "ExternalServiceError",
    "LLMError",
    "LLMConnectionError",
    "LLMResponseError",
    "LLMTimeoutError",
    "TTSError",
    "STTError",
    "ConfigurationError",
    "MissingConfigError",
]
