"""Custom exceptions for the TrustState SDK."""


class TrustStateError(Exception):
    """Raised when the TrustState API returns an error response.

    Attributes:
        message: Human-readable description of the error.
        status_code: HTTP status code returned by the API (if applicable).
    """

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"TrustStateError(message={self.message!r}, status_code={self.status_code})"
