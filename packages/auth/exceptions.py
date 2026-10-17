"""
Auth-related exception hierarchy.

Raise these from auth helpers; catch them in middleware to return
appropriate HTTP responses without leaking internal detail.
"""


class AuthError(Exception):
    """Base class for all authentication/authorization errors."""

    def __init__(self, message: str = "Authentication error") -> None:
        super().__init__(message)
        self.message = message


class InvalidTokenError(AuthError):
    """Raised when a JWT cannot be decoded or its signature is invalid."""

    def __init__(self, message: str = "Invalid or malformed token") -> None:
        super().__init__(message)


class ExpiredTokenError(AuthError):
    """Raised when a JWT has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message)


class InsufficientPermissionsError(AuthError):
    """Raised when the caller lacks the required role or permission."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)
