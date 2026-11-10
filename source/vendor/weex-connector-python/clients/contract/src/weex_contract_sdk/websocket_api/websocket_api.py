from __future__ import annotations

from typing import Any

from weex_common.signature import make_timestamp, sign_websocket_private
from weex_common.websocket import BaseWebSocketClient


class ContractWebSocketAPI:
    def __init__(self, configuration: Any) -> None:
        self._configuration = configuration
        self._client = BaseWebSocketClient(
            stream_url=configuration.stream_url,
            timeout=configuration.timeout,
            reconnect_delay=configuration.reconnect_delay,
            headers_factory=self._headers,
            allowed_domains=configuration.allowed_domains,
        )

    def _headers(self) -> dict[str, str]:
        timestamp = make_timestamp()
        headers = {"User-Agent": self._configuration.user_agent or "python-sdk"}
        if self._configuration.api_key and self._configuration.api_secret and self._configuration.passphrase:
            headers["ACCESS-KEY"] = self._configuration.api_key
            headers["ACCESS-TIMESTAMP"] = timestamp
            headers["ACCESS-PASSPHRASE"] = self._configuration.passphrase
            headers["ACCESS-SIGN"] = sign_websocket_private(
                secret=self._configuration.api_secret,
                timestamp=timestamp,
            )
        return headers

    def connect(self) -> None:
        self._client.connect()

    def subscribe(self, channel: str) -> None:
        self._client.subscribe_channel(channel)

    def unsubscribe(self, channel: str) -> None:
        self._client.unsubscribe_channel(channel)

    def receive(self) -> Any:
        return self._client.receive()

    def close(self) -> None:
        self._client.close()

    def subscribe_account(self) -> None:
        self.subscribe("account")

    def subscribe_positions(self) -> None:
        self.subscribe("positions")

    def subscribe_orders(self) -> None:
        self.subscribe("orders")

    def subscribe_fill(self) -> None:
        self.subscribe("fill")
