from __future__ import absolute_import


class ApiError(RuntimeError):
    def __init__(self, message, status_code=None, payload=None, url="", request_id=""):
        super(ApiError, self).__init__(str(message))
        self.status_code = status_code
        self.payload = payload
        self.url = str(url or "")
        self.request_id = str(request_id or "")


class ApiConfigurationError(ApiError):
    pass


class ApiConnectionError(ApiError):
    pass


class ApiAuthenticationError(ApiError):
    pass


class ApiResponseError(ApiError):
    pass
