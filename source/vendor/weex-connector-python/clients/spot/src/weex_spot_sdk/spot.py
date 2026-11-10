from __future__ import annotations

import platform

from weex_common.configuration import (
    ConfigurationRestAPI,
    ConfigurationWebSocketAPI,
    ConfigurationWebSocketStreams,
)

from . import metadata
from .rest_api import SpotRestAPI
from .websocket_api import SpotWebSocketAPI
from .websocket_streams import SpotWebSocketStreams

REST_API_PROD_URL = "https://api-spot.weex.com"
WS_API_PROD_URL = "wss://ws-spot.weex.com/v2/ws/private"
WS_STREAMS_PROD_URL = "wss://ws-spot.weex.com/v2/ws/public"


def _ua() -> str:
    return (
        f"{metadata.NAME}/{metadata.VERSION} "
        f"(Python/{platform.python_version()}; {platform.system()}; {platform.machine()})"
    )


class Spot:
    def __init__(
        self,
        config_rest_api: ConfigurationRestAPI | None = None,
        config_ws_api: ConfigurationWebSocketAPI | None = None,
        config_ws_streams: ConfigurationWebSocketStreams | None = None,
    ) -> None:
        self._rest_api_config = config_rest_api or ConfigurationRestAPI()
        self._ws_api_config = config_ws_api or ConfigurationWebSocketAPI()
        self._ws_streams_config = config_ws_streams or ConfigurationWebSocketStreams()
        self._rest_api: SpotRestAPI | None = None
        self._websocket_api: SpotWebSocketAPI | None = None
        self._websocket_streams: SpotWebSocketStreams | None = None

    @classmethod
    def from_env(cls, *, env_prefix: str = "WEEX_") -> "Spot":
        return cls(
            config_rest_api=ConfigurationRestAPI.from_env(
                env_prefix=env_prefix,
                base_url_env="WEEX_BASE_URL",
            ),
            config_ws_api=ConfigurationWebSocketAPI.from_env(
                env_prefix=env_prefix,
                stream_url_env="WEEX_WS_PRIVATE_URL",
            ),
            config_ws_streams=ConfigurationWebSocketStreams.from_env(
                stream_url_env="WEEX_WS_PUBLIC_URL",
            ),
        )

    @property
    def rest_api(self) -> SpotRestAPI:
        if self._rest_api is None:
            self._rest_api_config.user_agent = self._rest_api_config.user_agent or _ua()
            self._rest_api_config.base_path = self._rest_api_config.base_path or REST_API_PROD_URL
            self._rest_api = SpotRestAPI(self._rest_api_config)
        return self._rest_api

    @property
    def websocket_api(self) -> SpotWebSocketAPI:
        if self._websocket_api is None:
            self._ws_api_config.user_agent = self._ws_api_config.user_agent or _ua()
            self._ws_api_config.stream_url = self._ws_api_config.stream_url or WS_API_PROD_URL
            self._websocket_api = SpotWebSocketAPI(self._ws_api_config)
        return self._websocket_api

    @property
    def websocket_streams(self) -> SpotWebSocketStreams:
        if self._websocket_streams is None:
            self._ws_streams_config.user_agent = self._ws_streams_config.user_agent or _ua()
            self._ws_streams_config.stream_url = self._ws_streams_config.stream_url or WS_STREAMS_PROD_URL
            self._websocket_streams = SpotWebSocketStreams(self._ws_streams_config)
        return self._websocket_streams
