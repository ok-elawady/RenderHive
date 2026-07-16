from __future__ import absolute_import


class ApiError(RuntimeError):
    """Base error for all RenderHive API operations."""


class ApiConfigurationError(ApiError):
    """Raised when the API configuration is invalid."""


class ApiConnectionError(ApiError):
    """Raised when the API cannot be reached."""


class ApiHttpError(ApiError):
    def __init__(self, status_code, message, payload=None):
        super(ApiHttpError, self).__init__(message)
        self.status_code = int(status_code)
        self.payload = payload


class ApiResponseError(ApiError):
    """Raised when a API response is malformed or incomplete."""
