"""Shared local-only security boundary for Admin product surfaces."""

import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

# Exact host names (comma-separated) of a trusted local reverse proxy that serves Admin,
# e.g. a `*.localhost` route that only listens on 127.0.0.1. Empty keeps Admin local-only.
TRUSTED_HOSTS_ENV = "FCC_ADMIN_TRUSTED_HOSTS"


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _origin_hostname(origin: str) -> str | None:
    try:
        parsed = urlsplit(origin)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed.hostname


def _origin_is_local(origin: str | None) -> bool:
    if not origin:
        return True
    return _is_loopback_host(_origin_hostname(origin))


def _authority_hostname(authority: str | None) -> str | None:
    if not authority:
        return None
    try:
        parsed = urlsplit(f"//{authority}")
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed.hostname


def _authority_is_local(authority: str | None) -> bool:
    return _is_loopback_host(_authority_hostname(authority))


def _trusted_proxy_hosts() -> frozenset[str]:
    raw = os.environ.get(TRUSTED_HOSTS_ENV, "")
    return frozenset(host.strip().lower() for host in raw.split(",") if host.strip())


def _is_trusted_proxy_request(request: Request) -> bool:
    """Opt-in: a local reverse proxy serves Admin on an exact, configured host name.

    The client address is the proxy's, so it is not checked. Cross-site requests are
    still rejected because a present Origin must also be a trusted host, and DNS
    rebinding cannot match because the browser sends the attacker's host name.
    """
    trusted = _trusted_proxy_hosts()
    if not trusted:
        return False
    host = _authority_hostname(request.headers.get("host"))
    if host is None or host not in trusted:
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    return _origin_hostname(origin) in trusted


def require_loopback_admin(request: Request) -> None:
    """Allow Admin access only from the local machine or an opted-in local proxy host."""

    if _is_trusted_proxy_request(request):
        return
    client_host = request.client.host if request.client else None
    if not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")
    if not _authority_is_local(request.headers.get("host")):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")
    if not _origin_is_local(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")
