"""Pure initial-HTML SEO checks. No requests, rendering, or site changes."""

from collections import Counter, defaultdict
import json
import hashlib
import re

from bs4 import BeautifulSoup
import httpx

from .intake import safe_url
from .safety import DetectorError
from .seo_policy import HTTP_DOC, ROBOTS_DOC, origin

DOCS = {
    "title": "https://developers.google.com/search/docs/appearance/title-link",
    "description": "https://developers.google.com/search/docs/appearance/snippet",
    "canonical": "https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls",
    "robots": "https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag",
    "og": "https://ogp.me/",
    "lang": "https://www.w3.org/International/questions/qa-html-language-declarations",
    "headings": "https://www.w3.org/WAI/tutorials/page-structure/headings/",
    "links": "https://developers.google.com/search/docs/crawling-indexing/links-crawlable",
    "alt": "https://www.w3.org/WAI/tutorials/images/decision-tree/",
    "rendering": "https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics",
    "jsonld": "https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data",
    "itemlist": "https://schema.org/ItemList",
    "breadcrumb": "https://schema.org/BreadcrumbList",
}


def finding(check_id, url, result, severity, title, evidence, reason, recommendation, doc):
    return {"id": check_id, "url": url, "result": result, "severity": severity if result not in {"PASS", "NOT_APPLICABLE"} else "INFO",
            "title": title, "evidence": evidence, "reason": reason, "recommendation": recommendation,
            "documentation": [doc]}


def text(node):
    return " ".join(node.get_text(" ", strip=True).split())[:1000]


def directives(values):
    tokens = set()
    for value in values:
        tokens.update(re.findall(r"\b(?:noindex|index|nofollow|follow|none|all)\b", value.lower()))
    if "none" in tokens:
        tokens.update({"noindex", "nofollow"})
    if "all" in tokens:
        tokens.update({"index", "follow"})
    return {"directives": sorted(tokens), "indexing": "noindex" if "noindex" in tokens else "index_allowed",
            "following": "nofollow" if "nofollow" in tokens else "follow_allowed"}


def robots_directives(soup, headers):
    meta = [{"agent": str(t.get("name", "")).lower(), "value": str(t.get("content", ""))[:2000]}
            for t in soup.find_all("meta") if str(t.get("name", "")).lower() in {"robots", "yeti", "naverbot"}]
    x_values = headers.get_list("x-robots-tag")
    x_rules = []
    # Repeated headers and comma-separated bot prefixes retain their own scope.
    for value in x_values:
        agent = "robots"
        for part in value.split(","):
            part = part.strip()
            prefix = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", part)
            if prefix and prefix[1].lower() not in {"unavailable_after", "max-snippet", "max-image-preview", "max-video-preview"}:
                agent, part = prefix[1].lower(), prefix[2]
            x_rules.append({"agent": agent, "value": part[:2000]})
    raw = meta + x_rules
    general = [r["value"] for r in raw if r["agent"] == "robots"]
    yeti = general + [r["value"] for r in raw if r["agent"] in {"yeti", "naverbot"}]
    return {"meta": meta, "x_robots_tag": x_values, "general": directives(general), "Yeti": directives(yeti),
            "note": "태그 지시어의 정적 관찰입니다. Yeti의 모든 전용 지시어 지원 및 실제 색인은 별도 확인이 필요합니다."}


def inspect_html(page, site, *, indexing_goal="unknown"):
    soup = BeautifulSoup(page.html, "html.parser")
    head = soup.head or soup
    body = soup.body or soup
    visible = BeautifulSoup(str(body), "html.parser")
    for element in visible(["script", "style", "template", "noscript"]):
        element.decompose()
    visible_chars = len(visible.get_text(" ", strip=True))
    shell = bool(soup.select("#root, #app, #__next, [data-reactroot], script[src*='_next/'], script[type='module']"))
    rendering = shell and visible_chars < 80
    url, findings = page.url, []

    def add(key, result, severity, title, evidence, reason, advice, doc=None):
        findings.append(finding(key, url, result, severity, title, evidence, reason, advice, doc or DOCS[key.split(".")[0]]))

    def missing(result):
        return "NOT_VERIFIED" if rendering else result

    add("rendering.initial_html", "NOT_VERIFIED" if rendering else "PASS", "MEDIUM", "초기 HTML 검사 범위",
        {"app_shell_indicator": shell, "initial_visible_characters": visible_chars, "state": "RENDERING_REQUIRED" if rendering else "STATIC_HTML_CHECKED"},
        "앱 셸과 적은 본문은 렌더링 후 확인이 필요하다는 단서입니다. 실제 콘텐츠 부재를 증명하지 않습니다.",
        "렌더링 후 DOM과 공개 화면을 담당자가 대조하세요. 스크립트는 이번 분석에서 실행하지 않습니다.")
    titles = [" ".join(t.get_text(" ", strip=True).split()) for t in soup.find_all("title") if not t.find_parent(["svg", "math", "template"])]
    descriptions = [str(t.get("content", "")).strip() for t in soup.find_all("meta")
                    if str(t.get("name", "")).lower() == "description"]
    for key, values, label, absent, severity in (("title", titles, "Title", "ISSUE", "HIGH"),
                                               ("description", descriptions, "Meta Description", "WARNING", "MEDIUM")):
        state = missing(absent) if not any(values) else "PASS"
        if len(values) > 1:
            state = "ISSUE"
        add(key + ".declaration", state, severity if len(values) <= 1 else "MEDIUM", label + " 선언",
            {"count": len(values), "values": [v[:2000] for v in values[:20]], "excerpts_truncated": any(len(v) > 2000 for v in values)}, "비어 있거나 여러 번 선언된 메타데이터는 페이지 설명을 모호하게 할 수 있습니다. 검색 표시를 보장하는 검사는 아닙니다.",
            "페이지 내용에 맞는 고유한 " + label + "을 한 번 선언하세요. 렌더링 제한이 있으면 실제 DOM도 확인하세요.")

    base = page.url
    base_node = soup.find("base", href=True)
    if base_node:
        base = str(httpx.URL(url).join(base_node["href"]))
    canonicals = [str(t.get("href", "")) for t in head.find_all("link") if "canonical" in [str(r).lower() for r in t.get("rel", [])]]
    resolved, invalid = [], []
    for value in canonicals:
        try:
            if not value.strip() or "#" in value or any(ord(c) < 32 for c in value):
                raise ValueError("empty/fragment")
            resolved.append(safe_url(str(httpx.URL(base).join(value))))
        except (DetectorError, ValueError, httpx.InvalidURL):
            invalid.append(value[:500])
    relationship = "MISSING" if not canonicals else "INVALID" if invalid else "SELF" if resolved == [url] else "OTHER_URL"
    add("canonical.declaration", missing("WARNING") if not canonicals else "ISSUE" if invalid or len(canonicals) > 1 else "PASS" if relationship == "SELF" else "WARNING",
        "MEDIUM" if invalid or len(canonicals) > 1 else "LOW", "Canonical 선언 및 현재 URL 관계",
        {"raw": canonicals[:20], "resolved": resolved[:20], "invalid": invalid[:20], "relationship": relationship},
        "대표 URL 힌트를 확인합니다. 누락 자체는 심각한 오류가 아니며 다른 URL 지정도 의도적일 수 있습니다. 대상 URL은 별도 요청하지 않았습니다.",
        "중복 페이지 운영 의도와 대표 URL을 확인하고 필요할 때 유효한 canonical 한 개를 유지하세요.")
    og = defaultdict(list)
    for tag in head.find_all("meta"):
        key = str(tag.get("property", "")).lower()
        if key.startswith("og:"):
            og[key].append(str(tag.get("content", ""))[:1000])
    og_missing = [k for k in ("og:title", "og:type", "og:url", "og:image") if not any(og[k])]
    add("og.basic", missing("WARNING") if og_missing else "PASS", "LOW", "Open Graph 기본 정보",
        {"values": dict(og), "missing": og_missing}, "공유 미리보기용 정보입니다. 네이버 순위나 캐러셀 자격 판정과 다릅니다.", "페이지에 맞는 기본 Open Graph 정보를 검토하세요.")
    lang = str(soup.html.get("lang", "")) if soup.html else ""
    add("lang.declaration", "PASS" if re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", lang) else missing("WARNING"), "LOW", "HTML 언어 선언",
        {"lang": lang, "validation": "기본 태그 형식만 확인; 언어와 실제 콘텐츠 일치 미검증"}, "언어 선언은 문서 해석과 접근성에 도움을 줍니다.", "주요 문서 언어에 맞는 lang 값을 설정하세요.")

    robots = robots_directives(soup, page.headers)
    restricted = robots["Yeti"]["indexing"] == "noindex"
    robot_state = "PASS"
    if restricted:
        robot_state = "ISSUE" if indexing_goal == "index" else "PASS" if indexing_goal == "noindex" else "WARNING"
    elif indexing_goal == "noindex":
        robot_state = "WARNING"
    elif rendering and not robots["meta"] and not robots["x_robots_tag"]:
        robot_state = "NOT_VERIFIED"
    add("robots.indexing", robot_state, "HIGH" if robot_state == "ISSUE" else "MEDIUM", "Robots meta / X-Robots-Tag",
        {**robots, "customer_indexing_goal": indexing_goal}, "공개 응답의 지시어이며 실제 색인 상태가 아닙니다. 명시적 noindex가 없다고 색인되는 것은 아닙니다. 크롤링 차단 시 봇이 태그를 읽지 못할 수 있습니다.",
        "테스트·비공개 페이지는 noindex가 의도적일 수 있습니다. 고객의 색인 목적과 대조하고 Naver 지원 범위를 별도로 확인하세요.")
    add("robots.following", "WARNING" if robots["Yeti"]["following"] == "nofollow" else "NOT_VERIFIED" if rendering and not robots["meta"] and not robots["x_robots_tag"] else "PASS", "LOW", "링크 추적 지시어",
        {"general": robots["general"], "Yeti": robots["Yeti"]}, "nofollow는 링크 추적 제한 지시어입니다. 의도와 검색엔진 지원 여부 확인이 필요합니다.", "링크 추적 제한이 필요한 페이지인지 검토하세요.")

    headings = [{"level": int(t.name[1]), "text": text(t)} for t in body.find_all(re.compile(r"^h[1-6]$"))]
    counts = Counter(h["level"] for h in headings)
    skips = [i for i in range(1, len(headings)) if headings[i]["level"] > headings[i - 1]["level"] + 1]
    add("headings.structure", missing("WARNING") if not counts[1] else "WARNING" if counts[1] > 1 or skips else "PASS", "LOW", "H1~H6 콘텐츠 구조",
        {"counts": {f"h{i}": counts[i] for i in range(1, 7)}, "headings": headings[:100], "skipped_level_positions": skips[:100]},
        "제목 계층은 내용 이해와 접근성에 도움을 줍니다. H1 개수만으로 검색 오류를 확정하지 않습니다.", "주요 제목과 하위 제목의 논리적 계층을 검토하세요.")
    links, js, crawl_links = [], [], []
    for tag in body.find_all(["a", "area", "button"]):
        href = str(tag.get("href", ""))
        if tag.name == "button" and not (tag.get("onclick") or tag.get("role") == "link"):
            continue
        if not href or href == "#" or href.lower().startswith("javascript:"):
            if tag.name != "button" or tag.get("onclick") or tag.get("role") == "link":
                js.append({"element": tag.name, "text": text(tag), "href": href[:500], "onclick_present": tag.has_attr("onclick")})
            continue
        try:
            target = safe_url(str(httpx.URL(base).join(href)))
            if origin(target) == origin(site):
                links.append({"url": target, "text": text(tag)})
                if "nofollow" not in [str(r).lower() for r in tag.get("rel", [])]:
                    crawl_links.append(target)
        except (DetectorError, ValueError, httpx.InvalidURL):
            continue
    unique_links = list(dict.fromkeys(item["url"] for item in links))
    add("links.internal", "PASS" if links else missing("WARNING"), "LOW", "주요 내부 링크 및 대상",
        {"count": len(links), "unique_count": len(unique_links), "links": links[:100]}, "초기 HTML의 href만 관찰합니다. 모든 링크 응답을 확인한 결과가 아닙니다.", "주요 페이지에 일반 href 링크로 접근 가능한지 확인하세요.")
    add("links.javascript_navigation", "WARNING" if js else missing("PASS"), "LOW", "표준 href 없는 탐색 후보",
        {"count": len(js), "elements": js[:30]}, "빈 링크·JavaScript 링크·클릭 버튼은 탐색 후보입니다. 버튼이 실제 탐색 요소인지는 수동 확인이 필요합니다.", "페이지 이동 요소에는 유효한 href를 제공하고 실제 용도를 확인하세요.")
    images = body.find_all("img")
    absent_alt = [{"src": str(t.get("src", ""))[:500]} for t in images if not t.has_attr("alt")]
    add("alt.images", "WARNING" if absent_alt else missing("NOT_APPLICABLE") if not images else "PASS", "MEDIUM", "이미지 ALT 속성",
        {"image_count": len(images), "missing_count": len(absent_alt), "missing": absent_alt[:50], "empty_alt_count": sum(t.has_attr("alt") and not str(t["alt"]).strip() for t in images)},
        "ALT 누락과 장식 이미지용 빈 ALT를 구분합니다. 이미지 파일이나 설명의 정확성은 검사하지 않습니다.", "정보성 이미지에는 적절한 대체 텍스트를, 장식용 이미지에는 의도에 맞는 빈 ALT를 사용하세요.")
    structured_findings, structured = inspect_jsonld(soup, url)
    if rendering and not structured["script_count"]:
        for item in structured_findings:
            item["result"] = "NOT_VERIFIED"
    findings.extend(structured_findings)
    observations = {"title": [v[:2000] for v in titles[:20]], "description": [v[:2000] for v in descriptions[:20]], "canonical": resolved[:20],
                    "metadata_fingerprints": {k: hashlib.sha256(" ".join(v[0].lower().split()).encode()).hexdigest() if len(v) == 1 and v[0] else None for k, v in (("title", titles), ("description", descriptions))},
                    "rendering_state": "RENDERING_REQUIRED" if rendering else "STATIC_HTML_CHECKED",
                    "robots": robots, "internal_links": unique_links[:500], "internal_links_truncated": len(unique_links) > 500,
                    "crawl_links": list(dict.fromkeys(crawl_links))[:500] if robots["general"]["following"] != "nofollow" else [],
                    "structured_data": structured}
    return observations, findings


def inspect_jsonld(soup, url):
    scripts = [t for t in soup.find_all("script") if str(t.get("type", "")).split(";", 1)[0].strip().lower() == "application/ld+json"]
    errors, nodes, types, ids = [], [], [], []
    for index, script in enumerate(scripts):
        raw = script.string if script.string is not None else script.get_text()
        try:
            data = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-standard constant")))
            if not isinstance(data, (dict, list)):
                raise ValueError("JSON-LD 최상위는 객체 또는 배열이어야 합니다.")
            stack = [(data, False)]
            count = 0
            while stack:
                node, schema_context = stack.pop()
                count += 1
                if count > 10000:
                    raise ValueError("구조화 데이터 노드 한도 초과")
                if isinstance(node, list):
                    stack.extend((n, schema_context) for n in node)
                elif isinstance(node, dict):
                    context = node.get("@context")
                    contexts = context if isinstance(context, list) else [context]
                    local_schema = schema_context or any(isinstance(c, str) and c.rstrip("/") in {"http://schema.org", "https://schema.org"} for c in contexts)
                    declared = node.get("@type", [])
                    declared = [declared] if isinstance(declared, str) else declared if isinstance(declared, list) else []
                    for item in declared:
                        if not isinstance(item, str):
                            continue
                        if item.startswith(("http://schema.org/", "https://schema.org/")):
                            types.append(item.rsplit("/", 1)[-1])
                        elif local_schema and ":" not in item:
                            types.append(item)
                    if "@id" in node and "@type" in node:
                        ids.append(str(node["@id"])[:500])
                    stack.extend((v, local_schema) for k, v in node.items() if k != "@context")
            nodes.append({"script_index": index, "json_valid": True})
        except (ValueError, RecursionError) as exc:
            errors.append({"script_index": index, "error": "JSON 문법/지원 한도 오류", "line": getattr(exc, "lineno", None), "column": getattr(exc, "colno", None)})
    markers = []
    for match in re.finditer(r"yoast(?: seo)?|rank[ -]?math", str(soup), re.I):
        markers.append(match[0])
        if len(markers) >= 10:
            break
    count = Counter(types)
    repeated_ids = [key for key, n in Counter(ids).items() if n > 1]
    potential = count["ItemList"] > 1 or bool(repeated_ids) or bool(markers and count["ItemList"])
    evidence = {"script_count": len(scripts), "valid_scripts": nodes, "errors": errors, "schema_types": dict(count),
                "breadcrumb_count": count["BreadcrumbList"], "itemlist_count": count["ItemList"],
                "other_types": sorted(set(types) - {"BreadcrumbList", "ItemList"}),
                "repeated_typed_ids": repeated_ids[:30], "plugin_text_indicators": markers,
                "semantic_validation": "NOT_VERIFIED"}
    results = [finding("jsonld.syntax", url, "ISSUE" if errors else "PASS" if scripts else "NOT_APPLICABLE", "MEDIUM", "기존 JSON-LD 문법 및 유형", evidence,
                       "JSON 문법과 단순 schema.org 문맥만 확인합니다. 전체 JSON-LD 의미 확장·속성·검색 기능 적격성은 미검증이며 JSON-LD 부재 자체는 오류가 아닙니다.",
                       "문법 오류를 수정하고 유형별 공식 요구사항을 별도 검증하세요. 이번 분석은 새 데이터를 생성하지 않습니다.", DOCS["jsonld"]),
               finding("jsonld.duplication", url, "WARNING" if potential else "NOT_APPLICABLE" if not scripts else "PASS", "LOW", "기존 구조화 데이터의 중복 가능성",
                       {"itemlist_count": count["ItemList"], "breadcrumb_count": count["BreadcrumbList"], "repeated_typed_ids": repeated_ids[:30], "plugin_text_indicators": markers},
                       "BreadcrumbList와 일반 ItemList는 구분합니다. 여러 목록이나 플러그인 문자열은 충돌 확정 근거가 아닙니다.",
                       "기존 플러그인 출력·각 목록의 대상과 ID를 담당자가 대조한 뒤 향후 작업 범위를 결정하세요.", DOCS["itemlist"])]
    return results, evidence


def duplicate_findings(pages):
    results = []
    for key in ("title", "description"):
        groups = defaultdict(list)
        for page in pages:
            values = page.get("observations", {}).get(key, [])
            if page.get("state") == "ANALYZED" and len(values) == 1 and values[0].strip():
                fingerprint = page["observations"].get("metadata_fingerprints", {}).get(key)
                group_key = fingerprint or " ".join(values[0].lower().split())
                groups[group_key].append((page["final_url"], values[0]))
        comparable = sum(len(entries) for entries in groups.values())
        duplicates = [(entries[0][1], list(dict.fromkeys(e[0] for e in entries))) for entries in groups.values() if len(set(e[0] for e in entries)) > 1]
        if duplicates:
            for value, urls in duplicates:
                for url in urls:
                    results.append(finding(key + ".cross_page_duplicate", url, "WARNING", "MEDIUM", "페이지 사이의 중복 " + key,
                                           {"value": value, "urls": urls}, "분석한 서로 다른 URL에서 동일한 값이 발견되었습니다. 페이지 중복 여부나 의도까지 확정하지 않습니다.", "페이지 내용에 맞는 고유한 메타데이터가 필요한지 검토하세요.", DOCS[key]))
        else:
            results.append(finding(key + ".cross_page_duplicate", "AUDIT_SCOPE", "PASS" if comparable >= 2 else "NOT_VERIFIED", "LOW", "페이지 사이의 중복 " + key,
                                   {"comparable_page_count": comparable, "duplicates": []}, "단일 선언이 있는 분석 페이지끼리만 대조합니다. 두 페이지 미만이면 중복 여부를 검증할 수 없습니다.", "필요하면 고객이 승인한 비교 대상 페이지를 추가하세요.", DOCS[key]))
    return results
