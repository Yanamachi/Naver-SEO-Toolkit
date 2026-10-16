"""Conservative audit scope, RFC 9309 rule matching, and bounded sitemap XML."""

from dataclasses import dataclass
import re
from urllib.parse import parse_qsl, unquote
import xml.etree.ElementTree as ET

import httpx

from .intake import safe_url
from .safety import DetectorError

BOT = "EnvironmentDetector"
ROBOTS_DOC = "https://searchadvisor.naver.com/guide/seo-basic-robots"
RFC_DOC = "https://www.rfc-editor.org/rfc/rfc9309.html"
SITEMAP_DOC = "https://www.sitemaps.org/protocol.html"
HTTP_DOC = "https://developers.google.com/search/docs/crawling-indexing/http-network-errors"
PRIVATE_PATH = re.compile(r"(?:^|[/_.-])(?:wp-admin|wp-login|admin|administrator|login|logout|signin|signout|account|member|mypage|patient|checkout|cart|private|search|api|wp-json)(?:$|[/_.-])", re.I)
PRIVATE_QUERY = re.compile(r"^(?:s|q|query|search|keyword|page|offset|cursor|email|phone|name|patient|user|member|auth|code|key)$", re.I)


def origin(value):
    url = httpx.URL(value)
    return url.scheme, url.host, url.port


def scoped_url(value, site, *, discovered=False):
    result = safe_url(value)
    url = httpx.URL(result)
    if origin(result) != origin(site):
        raise DetectorError("AUDIT_SCOPE", "승인한 동일 출처(스킴·호스트·포트) 밖의 URL은 요청하지 않습니다.")
    path = url.path
    for _ in range(3):
        path = unquote(path)
    if PRIVATE_PATH.search(path) or "\\" in path or any(p == ".." for p in path.split("/")):
        raise DetectorError("EXCLUDED_PATH", "로그인·관리자·개인정보·검색 경로는 분석에서 제외합니다.")
    query = parse_qsl(url.query.decode("ascii"), keep_blank_values=True)
    if (discovered and query) or any(PRIVATE_QUERY.search(k) for k, _ in query):
        raise DetectorError("EXCLUDED_QUERY", "개인정보·인증·검색·페이지 순회 쿼리는 분석에서 제외합니다.")
    return result


def rep_octets(value):
    """RFC 9309 comparison: UTF-8 escapes, decode only ASCII unreserved."""
    result = []
    for char in value:
        result.append(char if ord(char) < 128 else "".join(f"%{b:02X}" for b in char.encode("utf-8")))
    def normalize(match):
        char = chr(int(match[1], 16))
        return char if char.isascii() and (char.isalnum() or char in "-._~") else match[0].upper()
    return re.sub(r"%([0-9a-fA-F]{2})", normalize, "".join(result))


@dataclass
class Robots:
    groups: list
    sitemaps: list
    usable: bool = True
    missing: bool = False

    def policy(self, agent, url):
        groups = []
        best = -1
        for group in self.groups:
            scores = [0 if ua == "*" else len(ua) for ua in group["agents"]
                      if ua == "*" or ua in agent.lower()]
            if not scores:
                continue
            score = max(scores)
            if score > best:
                groups, best = [group], score
            elif score == best:
                groups.append(group)
        parsed = httpx.URL(url)
        target = rep_octets(parsed.raw_path.decode("ascii"))
        matches = []
        for group in groups:
            for kind, rule in group["rules"]:
                rule = rep_octets(rule)
                end = rule.endswith("$")
                body = rule[:-1] if end else rule
                # Sequential glob segments avoid regex backtracking on untrusted rules.
                parts = body.split("*")
                matched = target.startswith(parts[0])
                position = len(parts[0])
                for part in parts[1:]:
                    found = target.find(part, position)
                    if found < 0:
                        matched = False
                        break
                    position = found + len(part)
                if end and (not target.endswith(parts[-1]) or (len(parts) == 1 and target != parts[0])):
                    matched = False
                if matched:
                    length = len(re.sub(r"%[0-9A-F]{2}", "x", body.replace("*", "")))
                    matches.append((length, kind == "allow", kind, rule))
        winner = max(matches, default=None)
        delays = [g["delay"] for g in groups if g["delay"] is not None]
        return {"agent": agent, "allowed": self.usable and (winner is None or winner[1]),
                "matched_agents": [g["agents"] for g in groups],
                "matched_rule": {"directive": winner[2], "path": winner[3]} if winner else None,
                "crawl_delay": max(delays, default=0), "policy_verified": self.usable}


def parse_robots(text):
    groups, maps = [], []
    group = None
    directives_started = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip().lstrip("\ufeff")
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "sitemap" and value:
            if value not in maps:
                maps.append(value)
            continue
        if key == "user-agent":
            if not value or not re.fullmatch(r"[A-Za-z_-]+|\*", value):
                continue
            if group is None or directives_started:
                group = {"agents": [], "rules": [], "delay": None}
                groups.append(group)
                directives_started = False
            group["agents"].append(value.lower())
        elif group is not None and key in {"allow", "disallow", "crawl-delay"}:
            directives_started = True
            if key in {"allow", "disallow"} and value.startswith("/"):
                group["rules"].append((key, value))
            elif key == "crawl-delay":
                try:
                    delay = float(value)
                    if 0 <= delay < float("inf"):
                        group["delay"] = delay
                except ValueError:
                    pass
    return Robots(groups, maps)


def parse_sitemap(text):
    """No DTD/entities or external resources; no recursive network parsing."""
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("DTD/ENTITY가 포함된 XML은 안전상 파싱하지 않습니다.")
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, RecursionError) as exc:
        raise ValueError("사이트맵 XML 문법 오류") from exc
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag not in {ns + "urlset", ns + "sitemapindex"}:
        raise ValueError("표준 네임스페이스의 urlset/sitemapindex가 아닙니다.")
    kind = root.tag[len(ns):]
    child_name = "url" if kind == "urlset" else "sitemap"
    nodes = root.findall(ns + child_name)
    if not nodes or len(nodes) > 50000:
        raise ValueError("사이트맵 항목 수가 비어 있거나 50,000개를 초과합니다.")
    urls = []
    for node in nodes:
        locs = node.findall(ns + "loc")
        if len(locs) != 1 or not (locs[0].text or "").strip():
            raise ValueError("사이트맵 항목에는 loc 한 개가 필요합니다.")
        try:
            urls.append(safe_url(locs[0].text.strip()))
        except (DetectorError, ValueError) as exc:
            raise ValueError("유효하지 않거나 안전하지 않은 loc URL") from exc
    return {"kind": kind, "urls": urls, "count": len(urls)}
