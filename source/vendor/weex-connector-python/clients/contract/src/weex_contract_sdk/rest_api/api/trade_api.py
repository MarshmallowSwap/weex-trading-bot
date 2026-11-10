from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class TradeApi(BaseApi):
    """Generated wrapper for Trade operations."""

    def delete_capi_v3_algo_open_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /capi/v3/algoOpenOrders` (`delete_capi_v3_algoOpenOrders`)."""
        return self._execute("delete_capi_v3_algoOpenOrders", request=request, **kwargs)

    def delete_capi_v3_algo_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /capi/v3/algoOrder` (`delete_capi_v3_algoOrder`)."""
        return self._execute("delete_capi_v3_algoOrder", request=request, **kwargs)

    def post_capi_v3_algo_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/algoOrder` (`post_capi_v3_algoOrder`)."""
        return self._execute("post_capi_v3_algoOrder", request=request, **kwargs)

    def get_capi_v3_all_algo_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/allAlgoOrders` (`get_capi_v3_allAlgoOrders`)."""
        return self._execute("get_capi_v3_allAlgoOrders", request=request, **kwargs)

    def delete_capi_v3_all_open_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /capi/v3/allOpenOrders` (`delete_capi_v3_allOpenOrders`)."""
        return self._execute("delete_capi_v3_allOpenOrders", request=request, **kwargs)

    def delete_capi_v3_batch_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /capi/v3/batchOrders` (`delete_capi_v3_batchOrders`)."""
        return self._execute("delete_capi_v3_batchOrders", request=request, **kwargs)

    def post_capi_v3_close_positions(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/closePositions` (`post_capi_v3_closePositions`)."""
        return self._execute("post_capi_v3_closePositions", request=request, **kwargs)

    def post_capi_v3_modify_tp_sl_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/modifyTpSlOrder` (`post_capi_v3_modifyTpSlOrder`)."""
        return self._execute("post_capi_v3_modifyTpSlOrder", request=request, **kwargs)

    def get_capi_v3_open_algo_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/openAlgoOrders` (`get_capi_v3_openAlgoOrders`)."""
        return self._execute("get_capi_v3_openAlgoOrders", request=request, **kwargs)

    def get_capi_v3_open_orders(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/openOrders` (`get_capi_v3_openOrders`)."""
        return self._execute("get_capi_v3_openOrders", request=request, **kwargs)

    def delete_capi_v3_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `DELETE /capi/v3/order` (`delete_capi_v3_order`)."""
        return self._execute("delete_capi_v3_order", request=request, **kwargs)

    def get_capi_v3_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/order` (`get_capi_v3_order`)."""
        return self._execute("get_capi_v3_order", request=request, **kwargs)

    def post_capi_v3_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/order` (`post_capi_v3_order`)."""
        return self._execute("post_capi_v3_order", request=request, **kwargs)

    def get_capi_v3_order_history(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/order/history` (`get_capi_v3_order_history`)."""
        return self._execute("get_capi_v3_order_history", request=request, **kwargs)

    def post_capi_v3_place_tp_sl_order(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/placeTpSlOrder` (`post_capi_v3_placeTpSlOrder`)."""
        return self._execute("post_capi_v3_placeTpSlOrder", request=request, **kwargs)

    def get_capi_v3_user_trades(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/userTrades` (`get_capi_v3_userTrades`)."""
        return self._execute("get_capi_v3_userTrades", request=request, **kwargs)

