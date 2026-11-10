from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any

import requests

from .configuration import validate_rest_base_path
from .errors import (
    ApiBusinessError,
    BadRequestError,
    ClientError,
    ForbiddenError,
    NetworkError,
    NotFoundError,
    RequiredError,
    ServerError,
    TooManyRequestsError,
    UnauthorizedError,
)
from .models import ApiResponse
from .signature import build_query, compact_json, make_timestamp, sign_rest


class RestTransport:
    def __init__(self, configuration: Any, operations: Mapping[str, dict[str, Any]]) -> None:
        self._configuration = configuration
        self._operations = operations
        self._session = configuration.session or requests.Session()

    def execute(
        self,
        operation_id: str,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ApiResponse:
        operation = self._operations.get(operation_id)
        if operation is None:
            raise ClientError(f"Unknown operation: {operation_id}")
        payload = dict(request or {})
        payload.update(kwargs)
        query, body, headers = self._split_request(operation, payload)
        return self._request(operation_id, operation, query=query, body=body, headers=headers)

    def _split_request(
        self,
        operation: Mapping[str, Any],
        request: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, str]]:
        headers = dict(request.get("headers") or {})
        if isinstance(request.get("query"), Mapping) or "body" in request:
            query = dict(request.get("query") or {})
            body_value = request.get("body")
            if isinstance(body_value, Mapping):
                body = dict(body_value)
            elif body_value is None:
                body = None
            else:
                body = {"value": body_value}
            return query, body, headers

        query_fields = set(operation.get("query_fields") or [])
        body_fields = set(operation.get("body_fields") or [])
        query: dict[str, Any] = {}
        body: dict[str, Any] = {}
        for key, value in request.items():
            if key in {"headers", "query", "body"} or value is None:
                continue
            if key in body_fields:
                body[key] = value
            elif key in query_fields:
                query[key] = value
            elif body_fields:
                body[key] = value
            else:
                query[key] = value
        return query, body or None, headers

    def _request(
        self,
        operation_id: str,
        operation: Mapping[str, Any],
        *,
        query: Mapping[str, Any] | None,
        body: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
    ) -> ApiResponse:
        method = str(operation["method"]).upper()
        path = str(operation["path"])
        base_path = validate_rest_base_path(
            self._configuration.base_path,
            allowed_domains=getattr(self._configuration, "allowed_domains", None),
        )
        base_path = (base_path or "").rstrip("/")
        if not base_path:
            raise ClientError("ConfigurationRestAPI.base_path is not set")

        query_string = build_query(query)
        body_text = compact_json(body) if body is not None else ""
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(self._configuration.base_headers or {})
        request_headers.update(headers or {})
        if self._configuration.user_agent:
            request_headers.setdefault("User-Agent", self._configuration.user_agent)

        if operation.get("auth"):
            if not self._configuration.api_key:
                raise RequiredError("api_key", "Missing API key for authenticated request")
            if not self._configuration.api_secret:
                raise RequiredError("api_secret", "Missing API secret for authenticated request")
            if not self._configuration.passphrase:
                raise RequiredError("passphrase", "Missing API passphrase for authenticated request")
            timestamp = make_timestamp()
            request_headers["ACCESS-KEY"] = self._configuration.api_key
            request_headers["ACCESS-TIMESTAMP"] = timestamp
            request_headers["ACCESS-PASSPHRASE"] = self._configuration.passphrase
            request_headers["ACCESS-SIGN"] = sign_rest(
                secret=self._configuration.api_secret,
                timestamp=timestamp,
                method=method,
                request_path=path,
                query_string=query_string,
                body_text=body_text,
            )

        url = base_path + path + (f"?{query_string}" if query_string else "")
        data = body_text.encode("utf-8") if body is not None else None
        attempts = 1 + (int(self._configuration.max_retries) if method == "GET" else 0)
        last_error: Exception | None = None

        for attempt in range(attempts):
            started = time.time()
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    data=data,
                    headers=request_headers,
                    timeout=self._configuration.timeout,
                )
                elapsed_ms = int((time.time() - started) * 1000)
                parsed = self._parse_body(response.text)
                if 200 <= response.status_code < 300:
                    return ApiResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        data=parsed,
                        raw_body=response.text,
                        elapsed_ms=elapsed_ms,
                        operation_id=operation_id,
                    )
                self._raise_http_error(
                    operation_id=operation_id,
                    status_code=response.status_code,
                    raw_body=response.text,
                    headers=response.headers,
                    parsed=parsed,
                )
            except requests.RequestException as exc:
                last_error = NetworkError(
                    f"Network request failed: {exc}",
                    operation_id=operation_id,
                )
                if attempt + 1 >= attempts:
                    raise last_error from exc

        raise last_error or ClientError(f"Unknown transport failure for {operation_id}")

    @staticmethod
    def _parse_body(raw_body: str) -> Any:
        if not raw_body:
            return None
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return raw_body

    @staticmethod
    def _raise_http_error(
        *,
        operation_id: str,
        status_code: int,
        raw_body: str,
        headers: Mapping[str, str],
        parsed: Any,
    ) -> None:
        error_cls = {
            400: BadRequestError,
            401: UnauthorizedError,
            403: ForbiddenError,
            404: NotFoundError,
            429: TooManyRequestsError,
        }.get(status_code, ServerError if status_code >= 500 else BadRequestError)
        if isinstance(parsed, dict) and ("code" in parsed or "msg" in parsed):
            raise ApiBusinessError(
                parsed.get("msg") or f"HTTP {status_code}",
                status_code=status_code,
                code=parsed.get("code"),
                headers=headers,
                raw_body=raw_body,
                operation_id=operation_id,
            )
        raise error_cls(
            f"HTTP {status_code}",
            status_code=status_code,
            headers=headers,
            raw_body=raw_body,
            operation_id=operation_id,
        )
