import socket

import pytest

from environment_detector.safety import DetectorError, public_ip, resolve_destination, validate_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com", "//example.com", "example.com",
    "http://user:pass@example.com", "https://example.com:8080",
    "http://localhost", "http://foo.localhost", "http://router.local", "http://a.internal",
    "http://metadata", "http://a.onion", "https://example.com\n", "http://example.com\\@127.0.0.1",
    "http://[fe80::1%25eth0]", "http://", "http://[broken", "",
])
def test_unsafe_url_rejected_before_dns(url, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Unsafe URL must not reach DNS")
    monkeypatch.setattr(socket, "getaddrinfo", unexpected)
    with pytest.raises(DetectorError):
        resolve_destination(url)


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.1.2", "192.168.1.2", "169.254.169.254",
    "0.0.0.0", "100.64.0.1", "192.0.2.1", "224.0.0.1", "255.255.255.255", "168.63.129.16",
    "::1", "::", "fc00::1", "fe80::1", "ff02::1", "2001:db8::1",
    "::ffff:8.8.8.8", "2002:0808:0808::1", "64:ff9b::808:808",
])
def test_unsafe_ips(address):
    assert not public_ip(address)
    literal = f"[{address}]" if ":" in address else address
    with pytest.raises(DetectorError):
        resolve_destination(f"https://{literal}")


@pytest.mark.parametrize("address", ["8.8.8.8", "93.184.216.34", "2606:4700:4700::1111"])
def test_public_ips(address):
    assert public_ip(address)


def test_mixed_dns_answers_blocked(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(DetectorError, match="Non-public"):
        resolve_destination("https://example.com")


def test_dns_error(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror("failed")
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    with pytest.raises(DetectorError) as error:
        resolve_destination("https://example.com")
    assert error.value.code == "DNS_ERROR"


@pytest.mark.parametrize("host", ["2130706433", "0x7f000001", "0177.0.0.1", "127.1"])
def test_alternative_ipv4_encodings_cannot_bypass_dns_check(host, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ])
    with pytest.raises(DetectorError):
        resolve_destination(f"http://{host}")


def test_normalization():
    assert str(validate_url("https://EXAMPLE.COM./a#fragment")) == "https://example.com/a"
