from __future__ import annotations

from typing import Mapping


class Error(Exception):
    pass


class RequiredError(Error):
    def __init__(self, field: str, error_message: str | None = None) -> None:
        self.field = field
        self.error_message = error_message or f"Missing required parameter: {field}"
        super().__init__(self.error_message)


class ClientError(Error):
    pass


class SignatureError(ClientError):
    pass


class NetworkError(Error):
    def __init__(self, message: str, *, operation_id: str = "", raw_body: str = "") -> None:
        self.operation_id = operation_id
        self.raw_body = raw_body
        super().__init__(message)


class HttpError(Error):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        headers: Mapping[str, str] | None = None,
        raw_body: str = "",
        operation_id: str = "",
    ) -> None:
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.raw_body = raw_body
        self.operation_id = operation_id
        super().__init__(message)


class BadRequestError(HttpError):
    pass


class UnauthorizedError(HttpError):
    pass


class ForbiddenError(HttpError):
    pass


class NotFoundError(HttpError):
    pass


class TooManyRequestsError(HttpError):
    pass


class ServerError(HttpError):
    pass


class ApiBusinessError(HttpError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | int | None = None,
        headers: Mapping[str, str] | None = None,
        raw_body: str = "",
        operation_id: str = "",
    ) -> None:
        self.code = code
        super().__init__(
            message,
            status_code=status_code,
            headers=headers,
            raw_body=raw_body,
            operation_id=operation_id,
        )
