from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class ApiResponse:
    status_code: int
    headers: Mapping[str, str]
    data: Any
    raw_body: str
    elapsed_ms: int
    operation_id: str = ""
