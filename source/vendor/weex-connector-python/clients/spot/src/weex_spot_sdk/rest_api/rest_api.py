from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse
from weex_common.transport import RestTransport

from .api.account_api import AccountApi
from .api.general_api import GeneralApi
from .api.market_api import MarketApi
from .api.rebate_api import RebateApi
from .api.trade_api import TradeApi
from .operations import OPERATIONS


class SpotRestAPI:
    def __init__(self, configuration: Any) -> None:
        self._transport = RestTransport(configuration, OPERATIONS)
        self.general_api = GeneralApi(self._transport)
        self.market_api = MarketApi(self._transport)
        self.trade_api = TradeApi(self._transport)
        self.account_api = AccountApi(self._transport)
        self.rebate_api = RebateApi(self._transport)

    def execute_operation(
        self,
        operation_id: str,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ApiResponse:
        return self._transport.execute(operation_id, request=request, **kwargs)
