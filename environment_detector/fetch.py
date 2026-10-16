"""Single-page GET with pinned public IP, verified TLS and bounded reads."""

from dataclasses import dataclass
from collections.abc import Callable
import time

import httpx

from .safety import DetectorError, resolve_destination, validate_url

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT = 10.0
TOTAL_TIMEOUT = 30.0


@dataclass
class Page:
    url: str
    status_code: int
    headers: httpx.Headers
    html: str
    redirects: list[dict]
    size_bytes: int


def fetch_page(value: str, *, transport: httpx.BaseTransport | None = None) -> Page:
    return fetch_resource(value, transport=transport)


def fetch_resource(value: str, *, transport: httpx.BaseTransport | None = None,
                   accepted_types: set[str] | None = frozenset({"text/html", "application/xhtml+xml"}),
                   require_success: bool = True, before_request: Callable[[str], None] | None = None,
                   timeout: float = TIMEOUT, max_bytes: int = MAX_BYTES) -> Page:
    """Same pinned transport for optional read-only text/XML audits.

    The default behavior is exactly the original HTML detector. The audit gate
    runs on every hop, including redirects, before DNS or a connection.
    """
    initial = validate_url(value)
    current = str(initial)
    redirects = []
    seen = set()
    https_seen = initial.scheme == "https"
    deadline = time.monotonic() + TOTAL_TIMEOUT
    try:
        for hop in range(MAX_REDIRECTS + 1):
            if before_request is not None:
                before_request(current)
            destination = resolve_destination(current)
            url = destination.url
            if url.host != initial.host:
                raise DetectorError("REDIRECT_SCOPE", "Cross-host redirect blocked; supply its approved URL directly.")
            if https_seen and url.scheme != "https":
                raise DetectorError("UNSAFE_REDIRECT", "HTTPS downgrade blocked.")
            https_seen = https_seen or url.scheme == "https"
            if str(url) in seen:
                raise DetectorError("REDIRECT_LOOP", "Redirect loop detected.")
            seen.add(str(url))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DetectorError("TIMEOUT", "Analysis time budget exceeded.")
            pinned = url.copy_with(host=destination.addresses[0])
            # Fresh connection pool per hop prevents SNI reuse between hostnames.
            with httpx.Client(
                transport=transport, trust_env=False, follow_redirects=False, verify=True,
                timeout=min(timeout, remaining),
            ) as client:
                with client.stream(
                    "GET", pinned,
                    headers={"Host": url.netloc.decode("ascii"),
                             "User-Agent": "EnvironmentDetector/0.1 (read-only)",
                             "Accept": "text/html,application/xhtml+xml",
                             "Accept-Encoding": "identity"},
                    extensions={"sni_hostname": url.host},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise DetectorError("INVALID_REDIRECT", "Redirect has no Location header.")
                        if hop == MAX_REDIRECTS:
                            raise DetectorError("TOO_MANY_REDIRECTS", "Redirect limit exceeded.")
                        # Validate raw Location before HTTPX normalizes control characters.
                        if any(ord(c) <= 32 or ord(c) == 127 for c in location) or "\\" in location:
                            raise DetectorError("UNSAFE_REDIRECT", "Unsafe Location header.")
                        current = str(url.join(location))
                        redirects.append({"url": str(url), "status_code": response.status_code,
                                          "location": current})
                        continue
                    if require_success and not 200 <= response.status_code < 300:
                        raise DetectorError("HTTP_ERROR", f"HTTP status {response.status_code}.")
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if accepted_types is not None and content_type not in accepted_types:
                        raise DetectorError("UNSUPPORTED_CONTENT", "Response is not declared HTML/XHTML.")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise DetectorError("UNSUPPORTED_ENCODING", "Server ignored identity encoding; compressed responses are rejected.")
                    body = bytearray()
                    for chunk in response.iter_raw():
                        if time.monotonic() > deadline:
                            raise DetectorError("TIMEOUT", "Analysis time budget exceeded.")
                        if len(body) + len(chunk) > max_bytes:
                            raise DetectorError("BODY_TOO_LARGE", "Response exceeds the configured byte limit.")
                        body.extend(chunk)
                    decoded = httpx.Response(200, headers=response.headers, content=bytes(body))
                    return Page(str(url), response.status_code, response.headers,
                                decoded.text, redirects, len(body))
    except DetectorError as exc:
        exc.redirects = redirects
        raise
    except httpx.TimeoutException as exc:
        raise DetectorError("TIMEOUT", "HTTP request timed out.") from exc
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        raise DetectorError("NETWORK_ERROR", "HTTP/TLS request failed or response was invalid.") from exc
    raise DetectorError("NETWORK_ERROR", "No page was retrieved.")
