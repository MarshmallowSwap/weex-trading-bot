from __future__ import annotations

from typing import Any

from weex_common.websocket import BaseWebSocketClient


class SpotWebSocketStreams:
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
        return {"User-Agent": self._configuration.user_agent or "python-sdk"}

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

    def subscribe_ticker(self, symbol: str) -> None:
        self.subscribe(f"ticker.{symbol}")

    def subscribe_trades(self, symbol: str) -> None:
        self.subscribe(f"trades.{symbol}")

    def subscribe_depth(self, symbol: str, level: int = 15) -> None:
        self.subscribe(f"depth.{symbol}.{level}")

    def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        price_type: str = "LAST_PRICE",
    ) -> None:
        self.subscribe(f"kline.{price_type}.{symbol}.{interval}")
