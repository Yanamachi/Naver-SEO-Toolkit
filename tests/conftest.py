"""Offline test inputs; these fixtures never establish real customer facts."""

import socket

import pytest

from environment_detector.detect import analyze


@pytest.fixture(autouse=True)
def deny_live_network(monkeypatch):
    """Tests may replace DNS with fakes and use MockTransport, never live sockets."""
    def forbidden(*args, **kwargs):
        pytest.fail("Regression tests must not perform live DNS or socket connections")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture
def legacy_environment():
    """Hand-built input for the legacy schema branch with no data_origin field.

    Deliberately independent of the marked JSON fixtures: never strip their origin
    to make them READY. Tests set their own clock when freshness is relevant.
    All resulting READY/COMPLETED assertions describe software behavior only.
    """
    html = '<meta name="generator" content="WordPress"><p>Legacy schema unit input</p>'
    headers = {"content-type": "text/html", "server": "synthetic-responder"}
    return {
        "schema_version": "1.0", "status": "ok", "analyzed_at": None,
        "request_url": "https://www.nasa.gov/", "final_url": "https://www.nasa.gov/",
        "http": {"status_code": 200, "size_bytes": len(html.encode()),
                 "redirects": [], "headers": headers},
        **analyze(headers, html, "https://www.nasa.gov/"), "errors": [],
    }
