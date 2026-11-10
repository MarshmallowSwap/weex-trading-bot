from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse

from .base_api import BaseApi


class AccountApi(BaseApi):
    """Generated wrapper for Account operations."""

    def get_account_balance(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/account/` (`getAccountBalance`)."""
        return self._execute("getAccountBalance", request=request, **kwargs)

    def get_bill_records(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /api/v3/account/bills` (`getBillRecords`)."""
        return self._execute("getBillRecords", request=request, **kwargs)

    def get_funding_bill_records(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `POST /api/v3/account/fundingBills` (`getFundingBillRecords`)."""
        return self._execute("getFundingBillRecords", request=request, **kwargs)

    def get_transfer_records(self, request: Mapping[str, Any] | None = None, /, **kwargs: Any) -> ApiResponse:
        """Execute `GET /api/v3/account/transferRecords` (`getTransferRecords`)."""
        return self._execute("getTransferRecords", request=request, **kwargs)

