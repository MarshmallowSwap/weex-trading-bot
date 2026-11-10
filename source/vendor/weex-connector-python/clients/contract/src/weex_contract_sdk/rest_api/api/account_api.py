from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class AccountApi(BaseApi):
    """Generated wrapper for Account operations."""

    def get_capi_v3_account_account_config(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/accountConfig` (`get_capi_v3_account_accountConfig`)."""
        return self._execute("get_capi_v3_account_accountConfig", request=request, **kwargs)

    def get_capi_v3_account_balance(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/balance` (`get_capi_v3_account_balance`)."""
        return self._execute("get_capi_v3_account_balance", request=request, **kwargs)

    def get_capi_v3_account_commission_rate(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/commissionRate` (`get_capi_v3_account_commissionRate`)."""
        return self._execute("get_capi_v3_account_commissionRate", request=request, **kwargs)

    def post_capi_v3_account_income(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/account/income` (`post_capi_v3_account_income`)."""
        return self._execute("post_capi_v3_account_income", request=request, **kwargs)

    def post_capi_v3_account_leverage(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/account/leverage` (`post_capi_v3_account_leverage`)."""
        return self._execute("post_capi_v3_account_leverage", request=request, **kwargs)

    def post_capi_v3_account_margin_type(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/account/marginType` (`post_capi_v3_account_marginType`)."""
        return self._execute("post_capi_v3_account_marginType", request=request, **kwargs)

    def post_capi_v3_account_modify_auto_append_margin(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/account/modifyAutoAppendMargin` (`post_capi_v3_account_modifyAutoAppendMargin`)."""
        return self._execute("post_capi_v3_account_modifyAutoAppendMargin", request=request, **kwargs)

    def get_capi_v3_account_position_all_position(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/position/allPosition` (`get_capi_v3_account_position_allPosition`)."""
        return self._execute("get_capi_v3_account_position_allPosition", request=request, **kwargs)

    def get_capi_v3_account_position_single_position(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/position/singlePosition` (`get_capi_v3_account_position_singlePosition`)."""
        return self._execute("get_capi_v3_account_position_singlePosition", request=request, **kwargs)

    def post_capi_v3_account_position_margin(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /capi/v3/account/positionMargin` (`post_capi_v3_account_positionMargin`)."""
        return self._execute("post_capi_v3_account_positionMargin", request=request, **kwargs)

    def get_capi_v3_account_symbol_config(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /capi/v3/account/symbolConfig` (`get_capi_v3_account_symbolConfig`)."""
        return self._execute("get_capi_v3_account_symbolConfig", request=request, **kwargs)

