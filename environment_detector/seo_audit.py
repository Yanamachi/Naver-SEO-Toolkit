"""Bounded read-only SEO audit of an existing consented customer project."""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import time
from uuid import uuid4

import httpx

from .fetch import MAX_BYTES, fetch_resource
from .intake import IntakeError, private_copy, read_object, safe_url
from .projects import write_json, write_text
from .report import is_synthetic, validate_result
from .safety import DetectorError
from .seo_checks import duplicate_findings, finding, inspect_html
from .seo_policy import BOT, HTTP_DOC, ROBOTS_DOC, SITEMAP_DOC, Robots, parse_robots, parse_sitemap, scoped_url


@dataclass(frozen=True)
class AuditOptions:
    max_pages: int = 20
    crawl: bool = False
    check_sitemaps: bool = False
    interval: float = 1.0
    timeout: float = 10.0
    max_bytes: int = MAX_BYTES
    indexing_goal: str = "unknown"

    def validate(self):
        if type(self.max_pages) is not int or not 1 <= self.max_pages <= 100:
            raise IntakeError("최대 페이지 수는 1~100이어야 합니다(기본 20).")
        if type(self.max_bytes) is not int or not 1024 <= self.max_bytes <= MAX_BYTES:
            raise IntakeError("최대 응답 크기는 1 KiB~2 MiB입니다.")
        if any(not math.isfinite(v) or not lo <= v <= hi for v, lo, hi in ((self.interval, 0.1, 30), (self.timeout, 0.1, 10))):
            raise IntakeError("요청 간격은 0.1~30초, 작업별 타임아웃은 0.1~10초입니다.")
        if self.indexing_goal not in {"index", "noindex", "unknown"}:
            raise IntakeError("색인 의도는 index/noindex/unknown입니다.")
        if type(self.crawl) is not bool or type(self.check_sitemaps) is not bool:
            raise IntakeError("내부 탐색·사이트맵 승인은 boolean이어야 합니다.")


class Collector:
    def __init__(self, site, options, transport=None, sleeper=time.sleep, clock=time.monotonic):
        self.site, self.options, self.transport = site, options, transport
        self.sleeper, self.clock = sleeper, clock
        self.robots = Robots([], [], usable=False)
        self.last_request = None
        self.requests = []
        self.backoff = False

    def get(self, url, kind):
        def gate(candidate):
            candidate = scoped_url(candidate, self.site)
            if len(self.requests) >= (self.options.max_pages + 4) * 4:
                raise DetectorError("REQUEST_LIMIT", "전체 GET 요청 한도를 소진했습니다.")
            delay = self.options.interval
            if kind != "robots":
                policy = self.robots.policy(BOT, candidate)
                if not policy["allowed"]:
                    raise DetectorError("ROBOTS_BLOCKED", "분석기 User-agent의 robots 정책이 차단 또는 미확인입니다.")
                if self.backoff:
                    raise DetectorError("SERVER_BACKOFF", "서버가 429/503을 반환하여 추가 요청을 중단했습니다.")
                if policy["crawl_delay"] > 30:
                    raise DetectorError("CRAWL_DELAY_LIMIT", "robots Crawl-delay가 30초를 초과하여 요청하지 않았습니다.")
                delay = max(delay, policy["crawl_delay"])
            if self.last_request is not None:
                wait = delay - (self.clock() - self.last_request)
                if wait > 0:
                    self.sleeper(wait)
            self.last_request = self.clock()
            self.requests.append({"url": candidate, "method": "GET", "kind": kind})
        page = fetch_resource(url, transport=self.transport, accepted_types=None, require_success=False,
                              before_request=gate, timeout=self.options.timeout, max_bytes=self.options.max_bytes)
        if page.status_code in {429, 503}:
            self.backoff = True
        return page


def load_project(folder):
    folder = Path(folder).absolute()
    for path in (folder, *folder.parents, *(folder / n for n in ("seo-audit.json", "seo-report.html", "history"))):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise IntakeError("심볼릭 링크·정션 프로젝트/출력 경로는 허용하지 않습니다.")
    if any((folder / n).exists() and not (folder / n).is_file() for n in ("seo-audit.json", "seo-report.html")):
        raise IntakeError("SEO 출력 경로는 일반 파일이어야 합니다.")
    project, intake, environment = (read_object(folder / name) for name in ("project.json", "intake.json", "environment.json"))
    try:
        validate_result(environment)
        if project["schema_version"] != "project-1.0" or intake["schema_version"] != "intake-1.0" or not isinstance(intake["request"], dict):
            raise ValueError("schema")
        request = intake["request"]
        targets = request.get("target_page_urls", [])
        if not isinstance(targets, list) or any(not isinstance(v, str) for v in targets):
            raise ValueError("target URLs")
        if not isinstance(project.get("job_id"), str):
            raise ValueError("job ID")
        if request.get("site_url") is not None and not isinstance(request["site_url"], str):
            raise ValueError("site URL")
        if not isinstance(request.get("requested_services", []), list) or any(not isinstance(v, str) for v in request.get("requested_services", [])):
            raise ValueError("services")
    except (KeyError, ValueError, TypeError) as exc:
        raise IntakeError("기존 고객 프로젝트의 JSON 형식을 확인하세요.") from exc
    return folder, project, intake, environment


def audit_project(folder, *, options=None, transport=None, sleeper=time.sleep, clock=time.monotonic, now=None):
    options = options or AuditOptions()
    options.validate()
    folder, project, intake, environment = load_project(folder)
    now = now or datetime.now(timezone.utc)
    request = intake["request"]
    environment_synthetic = is_synthetic(environment) or is_synthetic(project.get("environment", {}))
    result = {"schema_version": "seo-audit-1.0", "job_id": project["job_id"], "analyzed_at": now.isoformat(),
              "data_origin": "SYNTHETIC_TEST_FIXTURE_MOCK_HTTP" if transport is not None else "NOT_REQUESTED",
              "status": "BLOCKED", "options": asdict(options), "customer": {k: request.get(k) for k in ("company_name", "site_url", "requested_services")},
              "environment_reference": {"analyzed_at": environment.get("analyzed_at"), "data_origin": environment.get("data_origin", project.get("environment", {}).get("data_origin")),
                                        "synthetic": environment_synthetic, "refreshed": False},
              "scope": {"explicit_urls": request.get("target_page_urls") or [request.get("site_url") or "UNKNOWN"], "crawl_approved": options.crawl, "sitemaps_approved": options.check_sitemaps},
              "robots": {}, "sitemaps": [], "pages": [], "findings": [], "requests": [], "customer_questions": [],
              "limitations": ["공개 초기 HTML과 응답 헤더만 검사하며 JavaScript를 실행하지 않습니다.",
                              "실제 네이버 색인·순위·캐러셀 노출, 페이지 성능·Core Web Vitals는 미검증입니다.",
                              "서버 소스·관리자·로그인·권한·배포 가능성은 검사하지 않습니다.",
                              "모든 외부 자원·이미지·canonical·링크 대상에 자동 요청하지 않습니다.",
                              "사이트맵 XML의 기본 구조만 검사하며 전체 XSD/JSON-LD 의미 검증은 수행하지 않습니다.",
                              "환경 탐지 JSON은 과거 결과 그대로이며 이번 SEO 분석으로 최신화하지 않습니다."]}
    findings = result["findings"]

    def add(key, url, state, severity, title, evidence, reason, advice, doc):
        findings.append(finding(key, url, state, severity, title, evidence, reason, advice, doc))

    site = None
    fixture_only = (is_synthetic(project) or is_synthetic(intake)) and transport is None
    if fixture_only:
        result["data_origin"] = "SYNTHETIC_TEST_FIXTURE_NOT_REQUESTED"
        add("scope.synthetic", request.get("site_url") or "UNKNOWN", "NOT_VERIFIED", "HIGH", "가상 의뢰의 실제 HTTP 분석 차단",
            {"synthetic_project": True, "requests_sent": 0}, "가상 의뢰서의 모의 동의는 실제 고객 동의가 아닙니다.",
            "이 예제는 재현 스크립트 또는 --report-only로 확인하세요. 실제 고객은 별도 의뢰와 동의로 접수하세요.", ROBOTS_DOC)
    elif request.get("public_analysis_consent") is not True:
        add("scope.consent", request.get("site_url") or "UNKNOWN", "NOT_VERIFIED", "HIGH", "공개 영역 분석 동의 필요",
            {"public_analysis_consent": request.get("public_analysis_consent"), "requests_sent": 0}, "명시적 고객 동의 없이 사이트에 요청하지 않습니다.", "공개 영역 분석 동의를 확보한 정규 의뢰서로 접수하세요.", ROBOTS_DOC)
        result["customer_questions"].append("홈페이지 공개 영역의 읽기 전용 분석에 동의하시나요? 인증정보나 계정은 제공하지 마세요.")
    else:
        try:
            site = safe_url(request.get("site_url") or "")
            site = scoped_url(site, site)
        except (DetectorError, ValueError) as exc:
            add("scope.url", "UNKNOWN", "NOT_VERIFIED", "HIGH", "홈페이지 URL 검증 실패", {"code": getattr(exc, "code", "INVALID_URL")},
                "안전한 공개 홈페이지 URL을 확인하지 못했습니다.", "올바른 공개 HTTP(S) URL과 대상 범위를 확인하세요.", HTTP_DOC)
    if environment_synthetic:
        result["limitations"].append("연결된 환경 JSON은 가상 테스트 데이터입니다. 실제 CMS 검증 근거로 사용하지 않습니다.")
    if site:
        collector = Collector(site, options, transport, sleeper, clock)
        result["requests"] = collector.requests
        collect_robots(collector, result)
        explicit = result["scope"]["explicit_urls"]
        queue = list(explicit)
        seen, final_seen = set(), set()
        while queue and len(result["pages"]) < options.max_pages:
            candidate = queue.pop(0)
            if candidate in seen:
                continue
            seen.add(candidate)
            page_record = {"request_url": candidate, "final_url": None, "state": "NOT_VERIFIED", "http": None}
            result["pages"].append(page_record)
            try:
                candidate = scoped_url(candidate, site, discovered=candidate not in explicit)
                policies = {a: collector.robots.policy(a, candidate) for a in ("*", "Yeti", BOT)}
                add("robots.access", candidate, "NOT_VERIFIED" if not collector.robots.usable else "PASS" if policies["Yeti"]["allowed"] else "ISSUE" if options.indexing_goal == "index" else "WARNING",
                    "HIGH" if options.indexing_goal == "index" else "MEDIUM", "일반 / Yeti 접근 정책", policies,
                    "robots는 크롤링 정책입니다. 크롤링 허용과 실제 색인은 서로 다릅니다. 분석기는 자신의 정책도 준수합니다.", "고객의 공개·색인 의도와 Naver Yeti 정책을 대조하세요.", ROBOTS_DOC)
                page = collector.get(candidate, "page")
                page_record.update(final_url=page.url, http={"status_code": page.status_code, "redirects": page.redirects,
                                                           "size_bytes": page.size_bytes, "content_type": page.headers.get("content-type", "")})
                # A redirect may change the Yeti policy independently of our own UA.
                if page.url != candidate:
                    final_policy = collector.robots.policy("Yeti", page.url)
                    add("robots.final_access", page.url, "PASS" if final_policy["allowed"] else "WARNING", "MEDIUM", "최종 URL Yeti 접근 정책", final_policy,
                        "리다이렉트 후 경로의 정책은 최초 경로와 다를 수 있습니다.", "최종 경로의 공개 의도를 확인하세요.", ROBOTS_DOC)
                intentional_exclusion = options.indexing_goal == "noindex" and page.status_code in {401, 403, 404, 410}
                state = "PASS" if 200 <= page.status_code < 300 else "WARNING" if intentional_exclusion else "ISSUE"
                add("http.response", candidate, state, "LOW" if intentional_exclusion else "HIGH", "HTTP 상태 및 리다이렉트", {**page_record["http"], "customer_indexing_goal": options.indexing_goal},
                    "승인된 URL의 실제 응답입니다. 오류·접근 차단 응답의 본문을 정상 페이지 SEO로 평가하지 않습니다.", "오류인 경우 사이트 담당자에게 URL·공개 접근 정책·정상 응답을 확인하세요.", HTTP_DOC)
                if not 200 <= page.status_code < 300:
                    page_record["state"] = "HTTP_ERROR"
                    continue
                content_type = page.headers.get("content-type", "").split(";", 1)[0].lower().strip()
                if content_type not in {"text/html", "application/xhtml+xml"} or page.status_code in {204, 205}:
                    page_record["state"] = "NON_HTML"
                    add("http.html", page.url, "NOT_APPLICABLE", "INFO", "HTML 기반 검사 불가", {"content_type": content_type, "status_code": page.status_code},
                        "HTML 문서가 아닌 응답이므로 메타데이터를 평가하지 않았습니다.", "분석할 공개 HTML 페이지 URL을 확인하세요.", HTTP_DOC)
                    continue
                if page.url in final_seen:
                    page_record["state"] = "DUPLICATE_FINAL_URL"
                    add("http.duplicate_final", candidate, "NOT_APPLICABLE", "INFO", "이미 분석한 최종 URL", {"final_url": page.url},
                        "동일 최종 문서는 중복 SEO 평가에서 제외했습니다.", "리다이렉트와 대표 URL 운영 의도를 확인하세요.", HTTP_DOC)
                    continue
                final_seen.add(page.url)
                observations, checks = inspect_html(page, site, indexing_goal=options.indexing_goal)
                page_record.update(state="ANALYZED", observations=observations)
                findings.extend(checks)
                if options.crawl:
                    for link in observations["crawl_links"]:
                        try:
                            link = scoped_url(link, site, discovered=True)
                        except (DetectorError, ValueError):
                            continue
                        if link not in seen and link not in queue and len(queue) < options.max_pages * 25:
                            queue.append(link)
            except (DetectorError, httpx.InvalidURL, ValueError) as exc:
                code = getattr(exc, "code", "INVALID_URL")
                page_record.update(state="BLOCKED" if code in {"AUDIT_SCOPE", "EXCLUDED_PATH", "EXCLUDED_QUERY", "UNSAFE_URL", "UNSAFE_DESTINATION", "ROBOTS_BLOCKED", "CRAWL_DELAY_LIMIT", "REQUEST_LIMIT", "SERVER_BACKOFF"} else "FETCH_FAILED",
                                   error={"code": code, "message": str(exc)[:500]}, redirects=getattr(exc, "redirects", []))
                add("http.unverified", candidate or "UNKNOWN", "NOT_VERIFIED", "HIGH", "요청 실패 또는 보안·정책 차단", page_record["error"],
                    "페이지에 접근하지 못했으므로 SEO 요소의 누락으로 판정하지 않습니다.", "실패 사유와 승인 범위를 담당자가 검토하세요. 보안 차단을 우회하지 마세요.", HTTP_DOC)
        result["scope"]["remaining_url_count"] = len(queue)
        collect_sitemaps(collector, result)
        findings.extend(duplicate_findings(result["pages"]))
        if any(p["state"] == "ANALYZED" for p in result["pages"]):
            result["status"] = "PARTIAL" if queue or any(p["state"] not in {"ANALYZED", "DUPLICATE_FINAL_URL"} for p in result["pages"]) or any(f["result"] == "NOT_VERIFIED" for f in findings) else "COMPLETE"
        else:
            result["status"] = "BLOCKED"
    if options.indexing_goal == "unknown":
        result["customer_questions"].append("각 대상 페이지를 검색에 노출하려는지, 테스트·비공개·의도적인 noindex 페이지인지 알려주세요.")
    if any(p.get("observations", {}).get("rendering_state") == "RENDERING_REQUIRED" for p in result["pages"]):
        result["customer_questions"].append("JavaScript 렌더링 후 실제 화면과 주요 콘텐츠를 담당자가 확인할 수 있도록 공개 화면 자료를 전달해 주세요.")
    result["summary"] = {"page_count": len(result["pages"]), "analyzed_pages": sum(p["state"] == "ANALYZED" for p in result["pages"]),
                         "failed_pages": sum(p["state"] in {"HTTP_ERROR", "NON_HTML", "FETCH_FAILED", "BLOCKED"} for p in result["pages"]),
                         "request_count": len(result["requests"]), "results": dict(Counter(f["result"] for f in findings))}
    if transport is None and not fixture_only:
        observed = result["robots"].get("status_code") is not None or any(p.get("http") for p in result["pages"])
        result["data_origin"] = "OBSERVED_HTTP" if observed else "HTTP_ATTEMPTED" if result["requests"] else "NOT_REQUESTED"
    result = private_copy(result)
    save_audit(folder, project, intake, environment, result, now)
    return result


def collect_robots(collector, result):
    url = str(httpx.URL(collector.site).copy_with(path="/robots.txt", query=None, fragment=None))
    record = result["robots"]
    record.update(url=url, state="NOT_VERIFIED")
    try:
        page = collector.get(url, "robots")
        record.update(status_code=page.status_code, final_url=page.url, redirects=page.redirects,
                      content_type=page.headers.get("content-type", ""), size_bytes=page.size_bytes)
        if page.status_code in {404, 410}:
            collector.robots = Robots([], [], missing=True)
            record.update(state="MISSING", note="robots.txt 없음. robots 규칙으로는 크롤링을 막지 않음; 실제 접근/색인은 별도 확인.")
        elif page.status_code == 200 and page.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "text/plain" and page.size_bytes <= 500 * 1024:
            collector.robots = parse_robots(page.html)
            record.update(state="PARSED", groups=collector.robots.groups, declared_sitemaps=collector.robots.sitemaps)
        else:
            record.update(state="UNAVAILABLE", note="robots 응답이 차단·서버 오류·비표준 형식이어서 분석기 접근을 보수적으로 중단했습니다. Naver의 모든 4xx 처리와 동일하다는 뜻은 아닙니다.")
    except DetectorError as exc:
        record.update(error={"code": exc.code, "message": str(exc)}, redirects=getattr(exc, "redirects", []))
    result["findings"].append(finding("robots.file", url, "PASS" if record["state"] == "PARSED" else "WARNING" if record["state"] == "MISSING" else "NOT_VERIFIED", "MEDIUM", "robots.txt 존재 및 주요 정책", record.copy(),
                                      "루트 robots.txt의 공개 응답을 확인합니다. 존재 여부만으로 색인 상태를 판단하지 않습니다.", "일반 User-agent와 Yeti의 정책을 고객의 공개 의도와 함께 검토하세요.", ROBOTS_DOC))


def collect_sitemaps(collector, result):
    declared = collector.robots.sitemaps
    findings = result["findings"]
    if not collector.options.check_sitemaps or not declared:
        findings.append(finding("sitemap.scope", collector.site, "NOT_VERIFIED" if declared else "NOT_APPLICABLE" if collector.robots.usable else "NOT_VERIFIED", "LOW", "사이트맵 검사 범위",
                                {"declared_urls": declared[:100], "approved": collector.options.check_sitemaps}, "선언된 사이트맵만 별도 승인 시 최대 3개 문서를 읽습니다. 경로를 추측하지 않습니다.", "사이트맵 검사가 필요하면 범위를 확인하고 --check-sitemaps를 사용하세요.", SITEMAP_DOC))
        return
    queue, seen = list(declared[:100]), set()
    while queue and len(result["sitemaps"]) < 3:
        candidate = queue.pop(0)
        if candidate in seen:
            continue
        seen.add(candidate)
        record = {"url": candidate, "state": "NOT_VERIFIED"}
        result["sitemaps"].append(record)
        try:
            url = scoped_url(candidate, collector.site)
            page = collector.get(url, "sitemap")
            record.update(final_url=page.url, status_code=page.status_code, redirects=page.redirects)
            if page.status_code != 200:
                raise ValueError("사이트맵 HTTP 응답이 200이 아닙니다.")
            parsed = parse_sitemap(page.html)
            record.update(state="VALID_BASIC_XML", kind=parsed["kind"], declared_url_count=parsed["count"])
            checked, not_checked = [], 0
            for entry in parsed["urls"]:
                try:
                    scoped_url(entry, collector.site, discovered=True)
                except (DetectorError, ValueError):
                    not_checked += 1
                    continue
                if parsed["kind"] == "sitemapindex":
                    if entry not in seen and entry not in queue and len(queue) < 100:
                        queue.append(entry)
                    continue
                match = next((p for p in result["pages"] if entry in {p["request_url"], p["final_url"]}), None)
                if match and match.get("http"):
                    checked.append({"url": entry, "status_code": match["http"]["status_code"], "final_url": match["final_url"], "redirects": match["http"]["redirects"]})
                else:
                    not_checked += 1
            record.update(checked_urls=checked, unchecked_url_count=not_checked, url_sample=parsed["urls"][:100])
            bad = [p for p in checked if not 200 <= p["status_code"] < 300 or p["redirects"]]
            findings.append(finding("sitemap.validity", candidate, "PASS", "INFO", "사이트맵 XML 기본 유효성", record.copy(), "표준 루트·loc·URL의 기본 형식만 검사했습니다. 모든 등록 페이지 접근 검증이 아닙니다.", "등록 URL의 공개 상태와 최신성을 별도 관리하세요.", SITEMAP_DOC))
            findings.append(finding("sitemap.responses", candidate, "WARNING" if bad else "NOT_VERIFIED" if not_checked or not checked else "PASS", "MEDIUM", "사이트맵 등록 URL과 실제 응답",
                                    {"checked": checked, "unchecked_count": not_checked, "xml_kind": parsed["kind"]}, "이미 승인 범위에서 분석한 URL만 대조했습니다. 사이트맵 등록만으로 추가 페이지를 요청하지 않습니다.", "오류·리다이렉트 URL을 검토하고 미검증 URL은 추가 승인 후 확인하세요.", SITEMAP_DOC))
        except (DetectorError, ValueError) as exc:
            code = getattr(exc, "code", "INVALID_SITEMAP")
            record.update(state="INVALID" if isinstance(exc, ValueError) and not isinstance(exc, DetectorError) else "NOT_VERIFIED", error={"code": code, "message": str(exc)[:500]})
            findings.append(finding("sitemap.validity", candidate, "ISSUE" if record["state"] == "INVALID" else "NOT_VERIFIED", "MEDIUM", "사이트맵 접근·구조 오류", record.copy(),
                                    "잘못된 XML과 접근 실패·승인 범위 차단은 구분합니다.", "오류 사유에 따라 XML 또는 승인된 공개 URL을 확인하세요.", SITEMAP_DOC))
    if queue:
        findings.append(finding("sitemap.limit", collector.site, "NOT_VERIFIED", "LOW", "사이트맵 문서 검사 한도", {"remaining_documents": len(queue), "max_documents": 3},
                                "제한된 요청을 위해 최대 3개 문서만 처리했습니다.", "추가 사이트맵은 승인 범위를 정한 뒤 별도 검토하세요.", SITEMAP_DOC))


def save_audit(folder, project, intake, environment, result, now):
    from .seo_report import render_audit
    try:
        html = render_audit(project, intake, environment, result)
    except (KeyError, TypeError, ValueError) as exc:
        raise IntakeError("SEO JSON의 진단 결과·요약 형식을 확인하세요.") from exc
    existing = [folder / n for n in ("seo-audit.json", "seo-report.html") if (folder / n).exists()]
    if existing:
        history = folder / "history" / ("seo-" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
        history.mkdir(parents=True)
        for path in existing:
            (history / path.name).write_bytes(path.read_bytes())
    write_json(folder / "seo-audit.json", result)
    write_text(folder / "seo-report.html", html)


def regenerate_report(folder):
    """Offline HTML rebuild. Does not invoke any collector or DNS."""
    folder, project, intake, environment = load_project(folder)
    result = read_object(folder / "seo-audit.json")
    if result.get("schema_version") != "seo-audit-1.0" or result.get("job_id") != project["job_id"]:
        raise IntakeError("동일 프로젝트의 SEO JSON인지 확인하세요.")
    from .seo_report import render_audit
    try:
        html = render_audit(project, intake, environment, result)
    except (KeyError, TypeError, ValueError) as exc:
        raise IntakeError("SEO JSON의 진단 결과·요약 형식을 확인하세요.") from exc
    old = folder / "seo-report.html"
    if old.exists():
        history = folder / "history" / ("seo-report-" + uuid4().hex[:10])
        history.mkdir(parents=True)
        (history / old.name).write_bytes(old.read_bytes())
    write_text(old, html)
    return result
