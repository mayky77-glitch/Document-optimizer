#!/usr/bin/env python3
"""Parse and constrain local Qdrant URLs before shell scripts issue requests."""

from __future__ import annotations

import sys
from urllib.parse import SplitResult, urlsplit

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def fail() -> None:
    raise SystemExit(
        "QDRANT_URL must be http(s)://127.0.0.1:<numeric-port>, "
        "http(s)://localhost:<numeric-port>, or http(s)://[::1]:<numeric-port>; "
        "userinfo, path, query, and fragment are forbidden."
    )


def parse_loopback_url(value: str) -> SplitResult:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        fail()
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in LOOPBACK_HOSTS
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        fail()
    return parsed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} QDRANT_URL")
    parse_loopback_url(sys.argv[1])
