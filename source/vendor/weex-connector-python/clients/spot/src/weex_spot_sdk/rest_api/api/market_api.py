from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class MarketApi(BaseApi):
    """Generated wrapper for Market operations."""

    def get_depth(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/depth` (`getDepth`)."""
        return self._execute("getDepth", request=request, **kwargs)

    def get_klines(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/klines` (`getKlines`)."""
        return self._execute("getKlines", request=request, **kwargs)

    def get_ticker24_hr(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/ticker/24hr` (`getTicker24Hr`)."""
        return self._execute("getTicker24Hr", request=request, **kwargs)

    def get_book_ticker(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/ticker/bookTicker` (`getBookTicker`)."""
        return self._execute("getBookTicker", request=request, **kwargs)

    def get_ticker_price(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/ticker/price` (`getTickerPrice`)."""
        return self._execute("getTickerPrice", request=request, **kwargs)

    def get_recent_trades(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/market/trades` (`getRecentTrades`)."""
        return self._execute("getRecentTrades", request=request, **kwargs)

