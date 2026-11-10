from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class MarketApi(BaseApi):
    """Generated wrapper for Market operations."""

    def get_capi_v3_market_depth(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/depth` (`get_capi_v3_market_depth`)."""
        return self._execute("get_capi_v3_market_depth", request=request, **kwargs)

    def get_capi_v3_market_exchange_info(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/exchangeInfo` (`get_capi_v3_market_exchangeInfo`)."""
        return self._execute("get_capi_v3_market_exchangeInfo", request=request, **kwargs)

    def get_capi_v3_market_funding_rate(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/fundingRate` (`get_capi_v3_market_fundingRate`)."""
        return self._execute("get_capi_v3_market_fundingRate", request=request, **kwargs)

    def get_capi_v3_market_history_klines(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/historyKlines` (`get_capi_v3_market_historyKlines`)."""
        return self._execute("get_capi_v3_market_historyKlines", request=request, **kwargs)

    def get_capi_v3_market_index_price_klines(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/indexPriceKlines` (`get_capi_v3_market_indexPriceKlines`)."""
        return self._execute("get_capi_v3_market_indexPriceKlines", request=request, **kwargs)

    def get_capi_v3_market_klines(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/klines` (`get_capi_v3_market_klines`)."""
        return self._execute("get_capi_v3_market_klines", request=request, **kwargs)

    def get_capi_v3_market_mark_price_klines(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/markPriceKlines` (`get_capi_v3_market_markPriceKlines`)."""
        return self._execute("get_capi_v3_market_markPriceKlines", request=request, **kwargs)

    def get_capi_v3_market_open_interest(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/openInterest` (`get_capi_v3_market_openInterest`)."""
        return self._execute("get_capi_v3_market_openInterest", request=request, **kwargs)

    def get_capi_v3_market_premium_index(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/premiumIndex` (`get_capi_v3_market_premiumIndex`)."""
        return self._execute("get_capi_v3_market_premiumIndex", request=request, **kwargs)

    def get_capi_v3_market_symbol_price(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/symbolPrice` (`get_capi_v3_market_symbolPrice`)."""
        return self._execute("get_capi_v3_market_symbolPrice", request=request, **kwargs)

    def get_capi_v3_market_ticker_24hr(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/ticker/24hr` (`get_capi_v3_market_ticker_24hr`)."""
        return self._execute("get_capi_v3_market_ticker_24hr", request=request, **kwargs)

    def get_capi_v3_market_ticker_book_ticker(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/ticker/bookTicker` (`get_capi_v3_market_ticker_bookTicker`)."""
        return self._execute("get_capi_v3_market_ticker_bookTicker", request=request, **kwargs)

    def get_capi_v3_market_time(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/time` (`get_capi_v3_market_time`)."""
        return self._execute("get_capi_v3_market_time", request=request, **kwargs)

    def get_capi_v3_market_trades(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/market/trades` (`get_capi_v3_market_trades`)."""
        return self._execute("get_capi_v3_market_trades", request=request, **kwargs)

