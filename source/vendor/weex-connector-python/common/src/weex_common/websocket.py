from __future__ import annotations

import json
import time
from typing import Any, Callable

from .configuration import validate_stream_url
from .errors import ClientError
from .signature import compact_json

try:
    import websocket
except ImportError:
    websocket = None


class BaseWebSocketClient:
    def __init__(
        self,
        *,
        stream_url: str | None,
        timeout: float = 30.0,
        reconnect_delay: float = 1.5,
        headers_factory: Callable[[], dict[str, str]] | None = None,
        allowed_domains: tuple[str, ...] | None = None,
    ) -> None:
        self._stream_url = stream_url
        self._timeout = timeout
        self._reconnect_delay = reconnect_delay
        self._headers_factory = headers_factory
        self._allowed_domains = allowed_domains
        self._ws = None
        self._subscriptions: set[str] = set()

    def _headers(self) -> list[str]:
        if not self._headers_factory:
            return []
        return [f"{key}: {value}" for key, value in self._headers_factory().items() if value]

    def connect(self) -> None:
        stream_url = validate_stream_url(
            self._stream_url,
            field_name="BaseWebSocketClient.stream_url",
            allowed_domains=self._allowed_domains,
        )
        if not stream_url:
            raise ClientError("WebSocket stream URL is not configured")
        if websocket is None:
            raise ClientError("websocket-client is not installed")
        if self._ws is None:
            self._ws = websocket.create_connection(
                stream_url,
                timeout=self._timeout,
                header=self._headers(),
            )

    def reconnect(self) -> None:
        self.close()
        time.sleep(self._reconnect_delay)
        self.connect()
        for channel in sorted(self._subscriptions):
            self.send_json({"event": "subscribe", "channel": channel})

    def send_json(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            self.connect()
        try:
            self._ws.send(compact_json(payload))
        except Exception:
            self.reconnect()
            self._ws.send(compact_json(payload))

    def receive(self) -> Any:
        if self._ws is None:
            self.connect()
        try:
            raw = self._ws.recv()
        except Exception:
            self.reconnect()
            raw = self._ws.recv()
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(payload, dict) and payload.get("event") == "ping" and payload.get("time") is not None:
            self.send_json({"event": "pong", "time": payload["time"]})
        return payload

    def subscribe_channel(self, channel: str) -> None:
        self.send_json({"event": "subscribe", "channel": channel})
        self._subscriptions.add(channel)

    def unsubscribe_channel(self, channel: str) -> None:
        self.send_json({"event": "unsubscribe", "channel": channel})
        self._subscriptions.discard(channel)

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None
