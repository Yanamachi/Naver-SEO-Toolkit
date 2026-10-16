"""Validate destinations before any HTTP connection; never trust DNS twice."""

import ipaddress
import re
import socket
from dataclasses import dataclass

import httpx


class DetectorError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Destination:
    url: httpx.URL
    addresses: tuple[str, ...]


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # Azure's platform virtual IP is globally numbered but is not a public website.
    if address == ipaddress.ip_address("168.63.129.16"):
        return False
    # Reject mapped/transition addresses too; they may embed a private IPv4.
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped or address.sixtofour or address.teredo:
            return False
        if address in ipaddress.ip_network("64:ff9b::/96"):
            return False
    return address.is_global and not (
        address.is_multicast or address.is_unspecified or address.is_reserved
    )


def validate_url(value: str) -> httpx.URL:
    if not value or re.search(r"[\x00-\x20\x7f\\]", value):
        raise DetectorError("UNSAFE_URL", "URL contains whitespace, controls or backslashes.")
    try:
        url = httpx.URL(value)
    except (httpx.InvalidURL, ValueError) as exc:
        raise DetectorError("UNSAFE_URL", "Invalid URL.") from exc
    if url.scheme not in {"http", "https"} or not url.host:
        raise DetectorError("UNSAFE_URL", "An absolute HTTP(S) URL is required.")
    if url.userinfo or url.port not in {None, 80, 443}:
        raise DetectorError("UNSAFE_URL", "Credentials and ports other than 80/443 are blocked.")
    host = url.host.lower().rstrip(".")
    if "%" in host or host == "localhost" or host.endswith(
        (".localhost", ".local", ".internal", ".test", ".invalid", ".onion", ".home", ".lan")
    ):
        raise DetectorError("UNSAFE_URL", "Local, special-use or scoped hostnames are blocked.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host):
            raise DetectorError("UNSAFE_URL", "A public DNS hostname is required.")
    return url.copy_with(host=host, fragment=None)


def resolve_destination(value: str) -> Destination:
    url = validate_url(value)
    try:
        literal = ipaddress.ip_address(url.host)
    except ValueError:
        try:
            records = socket.getaddrinfo(
                url.host, url.port or (443 if url.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise DetectorError("DNS_ERROR", "DNS resolution failed.") from exc
        addresses = tuple(dict.fromkeys(record[4][0] for record in records))
    else:
        addresses = (str(literal),)
    if not addresses or not all(public_ip(address) for address in addresses):
        raise DetectorError("UNSAFE_DESTINATION", "Non-public or unsafe IP destination blocked.")
    return Destination(url, addresses)
