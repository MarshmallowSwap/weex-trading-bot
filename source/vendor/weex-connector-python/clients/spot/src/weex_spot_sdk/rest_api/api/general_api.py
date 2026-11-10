from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class GeneralApi(BaseApi):
    """Generated wrapper for General operations."""

    def get_coins(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/coins` (`getCoins`)."""
        return self._execute("getCoins", request=request, **kwargs)

    def get_exchange_info(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/exchangeInfo` (`getExchangeInfo`)."""
        return self._execute("getExchangeInfo", request=request, **kwargs)

    def ping(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/ping` (`ping`)."""
        return self._execute("ping", request=request, **kwargs)

    def get_server_time(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/time` (`getServerTime`)."""
        return self._execute("getServerTime", request=request, **kwargs)

