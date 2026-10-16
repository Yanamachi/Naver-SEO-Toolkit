import socket

import httpx
import pytest

from environment_detector import fetch
from environment_detector.safety import DetectorError


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
    ])


def response(status=200, headers=None, content=b"<html>ok</html>"):
    return httpx.Response(status, headers=headers or {"content-type": "text/html; charset=utf-8"},
                          stream=httpx.ByteStream(content))


def test_ip_pinning_host_sni_and_no_second_dns_lookup(monkeypatch):
    lookups = []
    def dns(*args, **kwargs):
        lookups.append(args[0])
        address = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    def handler(request):
        assert request.url.host == "93.184.216.34"
        assert request.url.path == "/path"
        assert request.url.query == b"q=1"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        assert request.headers["accept-encoding"] == "identity"
        assert request.method == "GET"
        assert "cookie" not in request.headers
        return response(content="<p>한글</p>".encode())
    page = fetch.fetch_page("https://example.com/path?q=1", transport=httpx.MockTransport(handler))
    assert page.html == "<p>한글</p>"
    assert page.url == "https://example.com/path?q=1"
    assert lookups == ["example.com"]


@pytest.mark.parametrize("target,code", [
    ("http://127.0.0.1/", "UNSAFE_DESTINATION"),
    ("http://169.254.169.254/", "UNSAFE_DESTINATION"),
    ("https://other.example/", "REDIRECT_SCOPE"),
    ("http://example.com/next", "UNSAFE_REDIRECT"),
    ("https://user:pass@example.com/", "UNSAFE_URL"),
    ("https://example.com:8080/", "UNSAFE_URL"),
    ("file:///etc/passwd", "UNSAFE_URL"),
    ("/bad\\path", "UNSAFE_REDIRECT"),
])
def test_unsafe_redirect_never_makes_second_request(target, code):
    requests = []
    def handler(request):
        requests.append(request)
        return response(302, {"location": target})
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com/", transport=httpx.MockTransport(handler))
    assert error.value.code == code
    assert len(requests) == 1


def test_redirect_rechecks_dns(monkeypatch):
    count = 0
    def dns(*args, **kwargs):
        nonlocal count
        count += 1
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8" if count == 1 else "10.0.0.1", 443))]
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com/", transport=httpx.MockTransport(
            lambda request: response(302, {"location": "/next"})))
    assert error.value.code == "UNSAFE_DESTINATION"
    assert count == 2


def test_relative_redirect_and_http_to_https():
    def handler(request):
        if request.url.path == "/":
            return response(301, {"location": "https://example.com/final", "set-cookie": "secret=1"})
        assert "cookie" not in request.headers
        return response()
    page = fetch.fetch_page("http://example.com/", transport=httpx.MockTransport(handler))
    assert page.url == "https://example.com/final"
    assert len(page.redirects) == 1


def test_http_upgrade_cannot_downgrade_again():
    requests = []
    def handler(request):
        requests.append(request)
        location = "https://example.com/secure" if len(requests) == 1 else "http://example.com/plain"
        return response(302, {"location": location})
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("http://example.com/", transport=httpx.MockTransport(handler))
    assert error.value.code == "UNSAFE_REDIRECT"
    assert len(requests) == 2


@pytest.mark.parametrize("status,headers,body,code", [
    (403, {}, b"forbidden", "HTTP_ERROR"),
    (500, {}, b"failed", "HTTP_ERROR"),
    (200, {"content-type": "image/png"}, b"png", "UNSUPPORTED_CONTENT"),
    (200, {}, b"no type", "UNSUPPORTED_CONTENT"),
    (200, {"content-type": "text/html", "content-encoding": "gzip"}, b"compressed", "UNSUPPORTED_ENCODING"),
    (200, {"content-type": "text/html"}, b"x" * (fetch.MAX_BYTES + 1), "BODY_TOO_LARGE"),
    (302, {}, b"", "INVALID_REDIRECT"),
], ids=["http403", "http500", "image", "missing-type", "compressed", "oversize", "no-location"])
def test_response_errors(status, headers, body, code):
    # A harmless extra header preserves the deliberately empty Content-Type case.
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com", transport=httpx.MockTransport(
            lambda request: response(status, {"x-test": "1", **headers}, body)))
    assert error.value.code == code


@pytest.mark.parametrize("exception,code", [
    (httpx.ReadTimeout("slow"), "TIMEOUT"),
    (httpx.ConnectError("certificate verify failed"), "NETWORK_ERROR"),
    (httpx.RemoteProtocolError("bad HTTP"), "NETWORK_ERROR"),
])
def test_network_errors(exception, code):
    def handler(request):
        raise exception
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com", transport=httpx.MockTransport(handler))
    assert error.value.code == code


@pytest.mark.parametrize("loop,code", [(True, "REDIRECT_LOOP"), (False, "TOO_MANY_REDIRECTS")])
def test_redirect_bounds(loop, code):
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        return response(302, {"location": "/" if loop else f"/{count}"})
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com/", transport=httpx.MockTransport(handler))
    assert error.value.code == code
    assert count <= fetch.MAX_REDIRECTS + 1


def test_deadline(monkeypatch):
    times = iter([0, 0, fetch.TOTAL_TIMEOUT + 1])
    monkeypatch.setattr(fetch.time, "monotonic", lambda: next(times))
    with pytest.raises(DetectorError) as error:
        fetch.fetch_page("https://example.com", transport=httpx.MockTransport(lambda req: response()))
    assert error.value.code == "TIMEOUT"
