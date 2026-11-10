from __future__ import annotations

from collections.abc import Iterable
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .errors import ClientError

DEFAULT_ALLOWED_DOMAINS = ("weex.com", "weex.tech")


def _prefix(prefix: str) -> str:
    return prefix if prefix.endswith("_") else prefix + "_"


def _normalize_allowed_domains(allowed_domains: Iterable[str] | None) -> tuple[str, ...]:
    values = allowed_domains or DEFAULT_ALLOWED_DOMAINS
    normalized: list[str] = []
    for value in values:
        domain = str(value).strip().lower().strip(".")
        if not domain:
            continue
        if any(char in domain for char in (":", "/", "@", "?", "#")):
            raise ClientError("allowed_domains entries must be bare hostnames or domain suffixes")
        if domain not in normalized:
            normalized.append(domain)
    if not normalized:
        raise ClientError("allowed_domains must include at least one hostname or domain suffix")
    return tuple(normalized)


def _host_allowed(host: str, allowed_domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _validate_endpoint_url(
    value: str | None,
    *,
    field_name: str,
    allowed_schemes: tuple[str, ...],
    allowed_domains: Iterable[str] | None = None,
) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in allowed_schemes:
        scheme_list = " or ".join(allowed_schemes)
        raise ClientError(f"{field_name} must use {scheme_list}")
    if parsed.username is not None or parsed.password is not None:
        raise ClientError(f"{field_name} must not embed credentials")
    if not parsed.hostname:
        raise ClientError(f"{field_name} must be an absolute URL")
    if parsed.query or parsed.fragment:
        raise ClientError(f"{field_name} must not include query parameters or fragments")

    normalized_domains = _normalize_allowed_domains(allowed_domains)
    host = parsed.hostname.rstrip(".").lower()
    if not _host_allowed(host, normalized_domains):
        allowed_list = ", ".join(normalized_domains)
        raise ClientError(f"{field_name} host '{host}' is not allowed; expected one of: {allowed_list}")
    return cleaned


def validate_rest_base_path(
    base_path: str | None,
    *,
    allowed_domains: Iterable[str] | None = None,
) -> str | None:
    return _validate_endpoint_url(
        base_path,
        field_name="ConfigurationRestAPI.base_path",
        allowed_schemes=("https",),
        allowed_domains=allowed_domains,
    )


def validate_stream_url(
    stream_url: str | None,
    *,
    field_name: str = "ConfigurationWebSocket.stream_url",
    allowed_domains: Iterable[str] | None = None,
) -> str | None:
    return _validate_endpoint_url(
        stream_url,
        field_name=field_name,
        allowed_schemes=("wss",),
        allowed_domains=allowed_domains,
    )


@dataclass(slots=True)
class ConfigurationRestAPI:
    base_path: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    timeout: float = 30.0
    max_retries: int = 0
    base_headers: dict[str, str] = field(default_factory=dict)
    user_agent: str | None = None
    session: Any = None
    allowed_domains: tuple[str, ...] = DEFAULT_ALLOWED_DOMAINS

    def __post_init__(self) -> None:
        self.allowed_domains = _normalize_allowed_domains(self.allowed_domains)
        self.base_path = validate_rest_base_path(
            self.base_path,
            allowed_domains=self.allowed_domains,
        )

    @classmethod
    def from_env(
        cls,
        *,
        env_prefix: str = "WEEX_",
        base_url_env: str = "WEEX_BASE_URL",
    ) -> "ConfigurationRestAPI":
        prefix = _prefix(env_prefix)
        return cls(
            base_path=os.getenv(base_url_env, "").strip() or None,
            api_key=os.getenv(f"{prefix}API_KEY", "").strip() or None,
            api_secret=os.getenv(f"{prefix}API_SECRET", "").strip() or None,
            passphrase=os.getenv(f"{prefix}API_PASSPHRASE", "").strip() or None,
        )


@dataclass(slots=True)
class ConfigurationWebSocketAPI:
    stream_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    timeout: float = 30.0
    reconnect_delay: float = 1.5
    user_agent: str | None = None
    allowed_domains: tuple[str, ...] = DEFAULT_ALLOWED_DOMAINS

    def __post_init__(self) -> None:
        self.allowed_domains = _normalize_allowed_domains(self.allowed_domains)
        self.stream_url = validate_stream_url(
            self.stream_url,
            field_name="ConfigurationWebSocketAPI.stream_url",
            allowed_domains=self.allowed_domains,
        )

    @classmethod
    def from_env(
        cls,
        *,
        env_prefix: str = "WEEX_",
        stream_url_env: str = "WEEX_WS_PRIVATE_URL",
    ) -> "ConfigurationWebSocketAPI":
        prefix = _prefix(env_prefix)
        return cls(
            stream_url=os.getenv(stream_url_env, "").strip() or None,
            api_key=os.getenv(f"{prefix}API_KEY", "").strip() or None,
            api_secret=os.getenv(f"{prefix}API_SECRET", "").strip() or None,
            passphrase=os.getenv(f"{prefix}API_PASSPHRASE", "").strip() or None,
        )


@dataclass(slots=True)
class ConfigurationWebSocketStreams:
    stream_url: str | None = None
    timeout: float = 30.0
    reconnect_delay: float = 1.5
    user_agent: str | None = None
    allowed_domains: tuple[str, ...] = DEFAULT_ALLOWED_DOMAINS

    def __post_init__(self) -> None:
        self.allowed_domains = _normalize_allowed_domains(self.allowed_domains)
        self.stream_url = validate_stream_url(
            self.stream_url,
            field_name="ConfigurationWebSocketStreams.stream_url",
            allowed_domains=self.allowed_domains,
        )

    @classmethod
    def from_env(
        cls,
        *,
        stream_url_env: str = "WEEX_WS_PUBLIC_URL",
    ) -> "ConfigurationWebSocketStreams":
        return cls(stream_url=os.getenv(stream_url_env, "").strip() or None)
