# -*- coding: utf-8 -*-
"""Probe the middleware ports referenced by ``application.yml``.

Unlike ``/health`` (which only knows what the port actually wired), this script
only answers one question: *is there something listening?*

Usage::

    .venv\\Scripts\\python.exe tools\\check_middleware.py
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.db.engine import jdbc_to_sqlalchemy_url  # noqa: E402
from app.settings import settings  # noqa: E402

TIMEOUT = 3.0


def tcp(host: str, port: int) -> str:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            sock.settimeout(TIMEOUT)
            return "open"
    except OSError as error:
        return f"closed ({type(error).__name__})"


def main() -> int:
    netloc = jdbc_to_sqlalchemy_url(
        settings.jdbc_url, settings.db_username, settings.db_password
    ).split("://", 1)[1].rpartition("@")[2].split("/")[0]
    db_host, _, db_port = netloc.partition(":")
    checks = [
        ("gaussdb", db_host, int(db_port or 5432)),
        ("redis", settings.redis_host, settings.redis_port),
        ("kafka", settings.kafka_bootstrap_servers.split(",")[0], 9092),
    ]
    for name, host, port in checks:
        if ":" in str(host):
            host, _, port_text = str(host).partition(":")
            port = int(port_text)
        print(f"{name:8s} {host}:{port} -> {tcp(str(host), int(port))}")

    scheme = getattr(settings, "es_scheme", "http")
    es_url = f"{scheme}://{settings.es_host}:{settings.es_port}"
    try:
        response = httpx.get(es_url, timeout=TIMEOUT)
        print(f"{'es':8s} {es_url} -> HTTP {response.status_code}")
        print(f"{'':8s} cluster: {response.json().get('version', {}).get('number', '?')}")
    except Exception as error:  # noqa: BLE001
        print(f"{'es':8s} {es_url} -> unreachable ({type(error).__name__})")
        return 0

    try:
        rows = httpx.get(f"{es_url}/_cat/indices", params={"format": "json", "h": "index,docs.count"},
                         timeout=TIMEOUT).json()
        for row in sorted(rows, key=lambda item: item.get("index", "")):
            print(f"{'':8s} {row.get('index'):<50s} docs={row.get('docs.count')}")
        if not rows:
            print(f"{'':8s} (no index)")
    except Exception as error:  # noqa: BLE001
        print(f"{'':8s} _cat/indices failed ({type(error).__name__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
