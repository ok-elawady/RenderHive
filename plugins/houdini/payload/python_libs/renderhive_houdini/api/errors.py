from __future__ import absolute_import


class ApiError(RuntimeError):
    """Base error for all RenderHive API operations."""

    def __init__(
        self,
        message,
        status_code=None,
        payload=None,
        url="",
        request_id="",
        retry_after=None,
    ):
        super(ApiError, self).__init__(str(message))
        self.status_code = int(status_code) if status_code is not None else None
        self.payload = payload
        self.url = str(url or "")
        self.request_id = str(request_id or "")
        self.retry_after = retry_after


class ApiConfigurationError(ApiError):
    """Raised when the API configuration is invalid."""


class ApiConnectionError(ApiError):
    """Raised when the API cannot be reached."""


class ApiContractError(ApiError):
    """Raised when the configured API contract is incomplete or invalid."""


class ApiHttpError(ApiError):
    def __init__(
        self,
        status_code,
        message,
        payload=None,
        url="",
        request_id="",
        retry_after=None,
    ):
        super(ApiHttpError, self).__init__(
            message,
            status_code=status_code,
            payload=payload,
            url=url,
            request_id=request_id,
            retry_after=retry_after,
        )


class ApiAuthenticationError(ApiHttpError):
    """Raised for HTTP 401 and 403 authentication/authorization failures."""


class ApiNotFoundError(ApiHttpError):
    """Raised when a requested API object no longer exists."""


class ApiRateLimitError(ApiHttpError):
    """Raised when the API rejects a request because of rate limiting."""


class ApiResponseError(ApiError):
    """Raised when an API response is malformed or incomplete."""
