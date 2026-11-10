from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from weex_common.models import ApiResponse


class BaseApi:
    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def _execute(
        self,
        operation_id: str,
        request: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ApiResponse:
        return self._transport.execute(operation_id, request=request, **kwargs)
