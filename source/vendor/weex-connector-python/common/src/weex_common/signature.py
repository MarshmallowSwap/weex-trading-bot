from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from collections.abc import Mapping
from typing import Any

from .errors import SignatureError


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _norm(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return compact_json(value)
    return str(value)


def build_query(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    pairs: list[tuple[str, str]] = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                pairs.append((key, _norm(item)))
        else:
            pairs.append((key, _norm(value)))
    return urllib.parse.urlencode(pairs, doseq=True)


def make_timestamp() -> str:
    return str(int(time.time() * 1000))


def sign_message(secret: str, message: str) -> str:
    if not secret:
        raise SignatureError("Missing API secret for signing")
    try:
        digest = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    except Exception as exc:
        raise SignatureError(f"Failed to sign request: {exc}") from exc
    return base64.b64encode(digest).decode("utf-8")


def sign_rest(
    *,
    secret: str,
    timestamp: str,
    method: str,
    request_path: str,
    query_string: str = "",
    body_text: str = "",
) -> str:
    payload = (
        f"{timestamp}{method.upper()}{request_path}"
        f"{('?' + query_string) if query_string else ''}{body_text}"
    )
    return sign_message(secret, payload)


def sign_websocket_private(
    *,
    secret: str,
    timestamp: str,
    request_path: str = "/v2/ws/private",
) -> str:
    return sign_message(secret, f"{timestamp}{request_path}")
