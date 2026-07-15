from __future__ import absolute_import


class BackendError(RuntimeError):
    """Base error for all RenderHive backend operations."""


class BackendConfigurationError(BackendError):
    """Raised when the backend configuration is invalid."""


class BackendConnectionError(BackendError):
    """Raised when the backend cannot be reached."""


class BackendHTTPError(BackendError):
    def __init__(self, status_code, message, payload=None):
        super(BackendHTTPError, self).__init__(message)
        self.status_code = int(status_code)
        self.payload = payload


class BackendResponseError(BackendError):
    """Raised when a backend response is malformed or incomplete."""
