from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class RebateApi(BaseApi):
    """Generated wrapper for Rebate operations."""

    def get_affiliate_assets(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/agency/getAssert` (`getAffiliateAssets`)."""
        return self._execute("getAffiliateAssets", request=request, **kwargs)

    def get_affiliate_deal_data(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/agency/getDealData` (`getAffiliateDealData`)."""
        return self._execute("getAffiliateDealData", request=request, **kwargs)

    def verify_referrals(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/agency/verifyReferrals` (`verifyReferrals`)."""
        return self._execute("verifyReferrals", request=request, **kwargs)

    def get_affiliate_commission(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/rebate/affiliate/getAffiliateCommission` (`getAffiliateCommission`)."""
        return self._execute("getAffiliateCommission", request=request, **kwargs)

    def get_affiliate_ui_ds(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/rebate/affiliate/getAffiliateUIDs` (`getAffiliateUIDs`)."""
        return self._execute("getAffiliateUIDs", request=request, **kwargs)

    def get_channel_user_trade_and_asset(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/rebate/affiliate/getChannelUserTradeAndAsset` (`getChannelUserTradeAndAsset`)."""
        return self._execute("getChannelUserTradeAndAsset", request=request, **kwargs)

    def get_internal_withdrawal_status(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/rebate/affiliate/getInternalWithdrawalStatus` (`getInternalWithdrawalStatus`)."""
        return self._execute("getInternalWithdrawalStatus", request=request, **kwargs)

    def internal_withdrawal(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /api/v3/rebate/affiliate/internalWithdrawal` (`internalWithdrawal`)."""
        return self._execute("internalWithdrawal", request=request, **kwargs)

    def query_sub_channel_transactions(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /api/v3/rebate/affiliate/querySubChannelTransactions` (`querySubChannelTransactions`)."""
        return self._execute("querySubChannelTransactions", request=request, **kwargs)

