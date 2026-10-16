"""Conservative rules over headers and parsed HTML, without executing scripts."""

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx

CATEGORIES = ("cms", "frontend", "backend", "server", "cdn")
SOURCES = {
    "wordpress_generator": "https://developer.wordpress.org/reference/functions/wp_generator/",
    "wordpress_assets": "https://learn.wordpress.org/lesson/understand-where-your-files-live/",
    "imweb_assets": "https://imweb.me/qna?mode=faq&q=27524",
    "cafe24_assets": "https://sdsupport.cafe24.com/module/product/detail.html",
    "next_assets": "https://nextjs.org/blog/next-7",
    "next_header": "https://nextjs.org/docs/pages/api-reference/config/next-config-js/poweredByHeader",
    "express_header": "https://expressjs.com/en/4x/api/application/",
    "php_header": "https://www.php.net/manual/en/ini.core.php",
    "server_header": "https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.4",
    "cloudflare_ray": "https://developers.cloudflare.com/speed/troubleshooting/slow-website/",
}


def unknown() -> dict:
    return {"name": "UNKNOWN", "confidence": 0.0, "evidence": []}


def analyze(headers: httpx.Headers | dict, html: str, url: str) -> dict:
    headers = httpx.Headers(headers)
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict[str, dict]] = {category: {} for category in CATEGORIES}

    def add(category, name, confidence, rule, kind, value, meaning):
        item = found[category].setdefault(
            name, {"name": name, "confidence": 0.0, "evidence": []},
        )
        item["confidence"] = max(item["confidence"], confidence)
        evidence = {"rule": rule, "source": kind, "value": value[:300],
                    "meaning": meaning, "reference": SOURCES[rule]}
        if evidence not in item["evidence"] and len(item["evidence"]) < 10:
            item["evidence"].append(evidence)

    for meta in soup.find_all("meta"):
        if str(meta.get("name", "")).lower() == "generator":
            generator = str(meta.get("content", ""))
            if re.fullmatch(r"WordPress(?:\s+[\d.]+)?", generator, re.I):
                add("cms", "WordPress", 0.95, "wordpress_generator", "html.meta.generator",
                    generator, "Page explicitly advertises WordPress; runtime is not verified.")

    for tag in soup.find_all(["script", "link", "img"]):
        attribute = "href" if tag.name == "link" else "src"
        value = tag.get(attribute)
        if not isinstance(value, str):
            continue
        if tag.name == "link" and not set(tag.get("rel", [])) & {"stylesheet", "preload", "modulepreload"}:
            continue
        try:
            asset = urlsplit(urljoin(url, value))
            host = (asset.hostname or "").lower().rstrip(".")
            if asset.scheme not in {"http", "https"}:
                continue
        except ValueError:
            continue
        kind = f"html.{tag.name}.{attribute}"
        if re.search(r"/wp-content/(?:themes|plugins|uploads)/", asset.path):
            add("cms", "WordPress", 0.65, "wordpress_assets", kind, value,
                "WordPress-style resource path; a static export or embedded resource is possible.")
        if host == "cdn.imweb.me":
            add("cms", "Imweb", 0.55, "imweb_assets", kind, value,
                "Imweb-hosted resource only; does not prove this page runs on Imweb.")
        if host == "img.echosting.cafe24.com":
            add("cms", "Cafe24", 0.55, "cafe24_assets", kind, value,
                "Cafe24 template resource only; does not prove Cafe24 hosting or runtime.")
        if tag.name in {"script", "link"} and asset.path.startswith("/_next/static/"):
            add("frontend", "Next.js", 0.8, "next_assets", kind, value,
                "Next.js build resource; backend and React runtime are not inferred.")

    powered = headers.get("x-powered-by", "")
    for pattern, category, name, rule in [
        (r"Next\.js", "frontend", "Next.js", "next_header"),
        (r"Express", "backend", "Express", "express_header"),
        (r"PHP(?:/[\d.]+)?", "backend", "PHP", "php_header"),
    ]:
        if re.fullmatch(pattern, powered.strip(), re.I):
            add(category, name, 0.9, rule, "http.header.x-powered-by", powered,
                "Advertised HTTP technology; header can be hidden or spoofed.")
    server = headers.get("server", "").strip()
    if server:
        # Server describes the responding edge, not necessarily the origin.
        add("server", server[:100], 0.9, "server_header", "http.header.server", server,
            "Server header as advertised by the responder; origin software is UNKNOWN.")
    ray = headers.get("cf-ray", "")
    if re.fullmatch(r"[0-9a-f]{16,32}-[a-z]{3}", ray, re.I):
        add("cdn", "Cloudflare", 0.9, "cloudflare_ray", "http.header.cf-ray", ray,
            "Cloudflare response marker; does not identify origin infrastructure.")
    return {
        "technologies": {key: list(items.values()) or [unknown()] for key, items in found.items()},
        "development_model": unknown(),
        "limitations": [
            "Confidence is a rule strength score, not a calibrated probability.",
            "Headers and HTML can be spoofed, stale, or produced by a static export.",
            "Resource-only CMS matches are candidates, not confirmed platform ownership.",
            "Custom development, origin stack, OS, database and hosting are UNKNOWN unless directly observable; no inference is made.",
            "Only the final HTML response is analyzed; no JavaScript or linked resources are fetched.",
        ],
    }
