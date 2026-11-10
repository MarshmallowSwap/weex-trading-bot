from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class TradeApi(BaseApi):
    """Generated wrapper for Trade operations."""

    def get_all_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/allOrders` (`getAllOrders`)."""
        return self._execute("getAllOrders", request=request, **kwargs)

    def get_my_trades(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/myTrades` (`getMyTrades`)."""
        return self._execute("getMyTrades", request=request, **kwargs)

    def cancel_open_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /api/v3/openOrders` (`cancelOpenOrders`)."""
        return self._execute("cancelOpenOrders", request=request, **kwargs)

    def get_open_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/openOrders` (`getOpenOrders`)."""
        return self._execute("getOpenOrders", request=request, **kwargs)

    def cancel_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /api/v3/order` (`cancelOrder`)."""
        return self._execute("cancelOrder", request=request, **kwargs)

    def get_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/order` (`getOrder`)."""
        return self._execute("getOrder", request=request, **kwargs)

    def place_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /api/v3/order` (`placeOrder`)."""
        return self._execute("placeOrder", request=request, **kwargs)

    def cancel_batch_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /api/v3/order/batch` (`cancelBatchOrders`)."""
        return self._execute("cancelBatchOrders", request=request, **kwargs)

