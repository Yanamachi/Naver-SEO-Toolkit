"""Fixed initial HTML, safe mock HTTP, and additive project CLI regressions."""

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys

from bs4 import BeautifulSoup
import httpx
import pytest

from environment_detector import cli
from environment_detector.fetch import Page
from environment_detector.intake import IntakeError
from environment_detector.projects import create_project
from environment_detector.safety import DetectorError
from environment_detector.seo_audit import AuditOptions, audit_project, regenerate_report
from environment_detector.seo_checks import inspect_html, duplicate_findings
from environment_detector.seo_policy import parse_robots, parse_sitemap, scoped_url

SITE = "https://hospital.example.com/"
HTML = (Path(__file__).parent / "fixtures/seo/normal.html").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def inspect(html=HTML, headers=None, goal="unknown"):
    return inspect_html(Page(SITE, 200, httpx.Headers(headers or {}), html, [], len(html.encode())), SITE, indexing_goal=goal)


def check(items, key):
    return next(f for f in items if f["id"] == key)


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Real HTTP forbidden"))


def project(tmp_path, *, consent=True, targets=None, site=SITE):
    data = {"company_name": "가상 SEO 병원", "industry": "테스트", "site_url": site, "requested_services": ["SEO"],
            "target_page_urls": targets if targets is not None else [site], "public_analysis_consent": consent}
    path = tmp_path / "source.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return create_project(path, projects_dir=tmp_path / "jobs", reuse_dir=tmp_path / "empty", now=NOW)[0]


def mock(routes, calls):
    def handler(request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "hospital.example.com"
        assert request.extensions["sni_hostname"] == "hospital.example.com"
        assert request.method == "GET" and "cookie" not in request.headers
        calls.append(str(request.url.raw_path.decode()))
        response = routes.get(request.url.path)
        if response is None:
            pytest.fail("Unexpected URL: " + request.url.path)
        status, body, headers = response
        return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body.encode()))
    return httpx.MockTransport(handler)


def audit(folder, routes=None, options=None, **kwargs):
    calls = []
    routes = routes or {"/robots.txt": (404, "", {}), "/": (200, HTML, {"content-type": "text/html; charset=utf-8"})}
    result = audit_project(folder, options=options, transport=mock(routes, calls), sleeper=lambda _: None, now=NOW, **kwargs)
    return result, calls


def test_normal_html_and_complete_finding_contract():
    obs, findings = inspect()
    assert not [f for f in findings if f["result"] in {"ISSUE", "WARNING"}]
    assert obs["structured_data"]["breadcrumb_count"] == 1
    assert obs["structured_data"]["itemlist_count"] == 0
    assert check(findings, "alt.images")["evidence"]["empty_alt_count"] == 1
    for f in findings:
        assert set(f) == {"id", "url", "result", "severity", "title", "evidence", "reason", "recommendation", "documentation"}
        assert f["reason"] and f["recommendation"] and f["evidence"]
        assert all(url.startswith("https://") for url in f["documentation"])


def test_svg_title_is_not_a_duplicate_page_title():
    _, findings = inspect(HTML.replace("</body>", "<svg><title>도형 설명</title></svg></body>"))
    assert check(findings, "title.declaration")["evidence"]["count"] == 1


def test_long_metadata_does_not_create_false_duplicate_from_excerpt():
    pages = []
    for suffix in ("A", "B"):
        obs, _ = inspect(HTML.replace("가상 병원 진료 안내", "x" * 3000 + suffix))
        pages.append({"state": "ANALYZED", "final_url": SITE + suffix, "observations": obs})
    result = [f for f in duplicate_findings(pages) if f["id"] == "title.cross_page_duplicate"]
    assert len(result) == 1 and result[0]["result"] == "PASS"


def test_missing_metadata_severities_and_canonical_not_critical():
    _, findings = inspect('<html><body><p>공개 정적 페이지</p></body></html>')
    assert check(findings, "title.declaration")["result"] == "ISSUE"
    assert check(findings, "title.declaration")["severity"] == "HIGH"
    assert check(findings, "description.declaration")["result"] == "WARNING"
    assert check(findings, "canonical.declaration")["severity"] == "LOW"
    assert check(findings, "jsonld.syntax")["result"] == "NOT_APPLICABLE"


def test_multiple_title_and_description_and_cross_page_duplicates():
    html = HTML.replace("</title>", "</title><title>두 번째 제목</title>") + '<meta name="DESCRIPTION" content="중복">'
    _, findings = inspect(html)
    assert check(findings, "title.declaration")["result"] == "ISSUE"
    assert check(findings, "description.declaration")["result"] == "ISSUE"
    obs, _ = inspect()
    pages = [{"state": "ANALYZED", "final_url": SITE + suffix, "observations": obs} for suffix in ("", "doctors")]
    result = duplicate_findings(pages)
    assert len(result) == 4
    assert all(f["result"] == "WARNING" for f in result)
    assert all(f["result"] == "NOT_VERIFIED" for f in duplicate_findings(pages[:1]))
    assert all(f["result"] == "NOT_VERIFIED" for f in duplicate_findings([{**pages[0], "state": "HTTP_ERROR"}]))


@pytest.mark.parametrize("target,expected", [("/other", "WARNING"), ("javascript:alert(1)", "ISSUE"), ("http://127.0.0.1/", "ISSUE"), ("", "ISSUE")])
def test_canonical_relationship(target, expected):
    _, findings = inspect(HTML.replace('href="' + SITE + '"', 'href="' + target + '"'))
    assert check(findings, "canonical.declaration")["result"] == expected


@pytest.mark.parametrize("goal,state", [("unknown", "WARNING"), ("index", "ISSUE"), ("noindex", "PASS")])
def test_noindex_compared_to_explicit_customer_goal(goal, state):
    _, findings = inspect(HTML.replace("</head>", '<meta name="robots" content="noindex,nofollow"></head>'), goal=goal)
    assert check(findings, "robots.indexing")["result"] == state
    assert check(findings, "robots.following")["result"] == "WARNING"


def test_x_robots_general_yeti_and_other_bot_are_separate():
    obs, _ = inspect(headers=[("x-robots-tag", "googlebot: noindex, nofollow"), ("x-robots-tag", "yeti: nofollow")])
    assert obs["robots"]["general"]["indexing"] == "index_allowed"
    assert obs["robots"]["Yeti"]["indexing"] == "index_allowed"
    assert obs["robots"]["Yeti"]["following"] == "nofollow"
    obs, _ = inspect(headers={"x-robots-tag": "none"})
    assert obs["robots"]["general"]["indexing"] == "noindex"


def test_links_headings_alt_and_base_url():
    html = HTML.replace("</head>", '<base href="/section/"></head>').replace("</body>", '<h4>계층 건너뛰기</h4><a onclick="go()">탐색</a><a href="javascript:go()">실행</a><a href="relative">상대경로</a><img src="x.jpg"></body>')
    obs, findings = inspect(html)
    assert SITE + "section/relative" in obs["internal_links"]
    assert check(findings, "links.javascript_navigation")["evidence"]["count"] == 2
    assert check(findings, "headings.structure")["result"] == "WARNING"
    assert check(findings, "alt.images")["evidence"]["missing_count"] == 1


def test_rendering_shell_does_not_assert_missing_real_content():
    obs, findings = inspect('<html><head></head><body><div id="root"></div><script src="/app.js"></script></body></html>')
    assert obs["rendering_state"] == "RENDERING_REQUIRED"
    for key in ("title.declaration", "description.declaration", "canonical.declaration", "headings.structure", "alt.images", "jsonld.syntax"):
        assert check(findings, key)["result"] == "NOT_VERIFIED"


@pytest.mark.parametrize("raw", ['{"@type":', 'NaN', '"scalar"', '{"a":NaN}'])
def test_jsonld_invalid(raw):
    _, findings = inspect('<html><script type="application/ld+json">' + raw + '</script></html>')
    result = check(findings, "jsonld.syntax")
    assert result["result"] == "ISSUE"
    assert result["evidence"]["errors"]


def test_schema_graph_plugin_and_itemlist_ambiguity():
    raw = {"@context": "https://schema.org", "@graph": [{"@type": "BreadcrumbList"}, {"@type": "ItemList", "@id": "#x"}, {"@type": "ItemList", "@id": "#x"}, {"@type": "Organization"}]}
    obs, findings = inspect('<html><!-- Yoast SEO --><script type="application/ld+json">' + json.dumps(raw) + '</script></html>')
    assert obs["structured_data"]["schema_types"]["ItemList"] == 2
    assert obs["structured_data"]["breadcrumb_count"] == 1
    assert check(findings, "jsonld.duplication")["result"] == "WARNING"
    assert "확정" in check(findings, "jsonld.duplication")["reason"]
    obs, _ = inspect('<script type="application/ld+json">{"@context":"https://other.example/","@type":"ItemList"}</script>')
    assert not obs["structured_data"]["schema_types"]


def test_robots_yeti_specific_longest_match_allow_tie_and_percent_encoding():
    robots = parse_robots('''User-agent: *
Disallow: /
User-agent: Yeti
Disallow: /private/*
Allow: /private/public$
Disallow: /a
Allow: /a
Disallow: /café
Crawl-delay: 2
Sitemap: https://hospital.example.com/map.xml''')
    assert not robots.policy("*", SITE)["allowed"]
    assert robots.policy("Yeti", SITE)["allowed"]
    assert robots.policy("Yeti", SITE + "private/public")["allowed"]
    assert not robots.policy("Yeti", SITE + "private/public/extra")["allowed"]
    assert robots.policy("Yeti", SITE + "%61")["allowed"]
    assert not robots.policy("Yeti", SITE + "caf%C3%A9")["allowed"]
    assert robots.policy("Yeti", SITE)["crawl_delay"] == 2
    assert robots.sitemaps == [SITE + "map.xml"]


def test_robots_merged_groups_wildcards_and_empty_disallow():
    robots = parse_robots('User-agent: yeti\nDisallow: /one\nUser-agent: yeti\nDisallow: /two\nAllow: /file*.pdf$\nDisallow:\n')
    assert not robots.policy("Yeti", SITE + "one")["allowed"]
    assert not robots.policy("Yeti", SITE + "two")["allowed"]
    assert robots.policy("Yeti", SITE)["allowed"]
    assert parse_robots('User-agent: *\nDisallow: /x*a*b$').policy("Yeti", SITE + "xab_tail_ab")["allowed"] is False


@pytest.mark.parametrize("value", ["http://127.0.0.1", "https://evil.example/", SITE + "wp-admin/", SITE + "account", SITE + "?q=patient", SITE + "%61dmin/", SITE + "?token=SECRET", "file:///x", SITE + "?email=private@example.com"])
def test_scope_exclusions(value):
    with pytest.raises(DetectorError):
        scoped_url(value, SITE)


def xml(urls, kind="urlset"):
    tag = "url" if kind == "urlset" else "sitemap"
    return '<' + kind + ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<' + tag + '><loc>' + u + '</loc></' + tag + '>' for u in urls) + '</' + kind + '>'


@pytest.mark.parametrize("value", ["<bad", "<urlset/>", xml([]), '<!DOCTYPE x [<!ENTITY a "x">]><x/>', xml(["http://127.0.0.1"]), xml(["relative/path"])])
def test_invalid_sitemap(value):
    with pytest.raises(ValueError):
        parse_sitemap(value)


def test_project_end_to_end_preserves_old_artifacts_and_redacts(tmp_path):
    folder = project(tmp_path)
    before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    result, calls = audit(folder)
    assert calls == ["/robots.txt", "/"]
    assert result["summary"]["analyzed_pages"] == 1
    assert result["summary"]["failed_pages"] == 0
    assert result["data_origin"].startswith("SYNTHETIC_TEST_FIXTURE")
    assert all((folder / name).read_bytes() == raw for name, raw in before.items())
    assert json.loads((folder / "seo-audit.json").read_text(encoding="utf-8")) == result
    soup = BeautifulSoup((folder / "seo-report.html").read_text(encoding="utf-8"), "html.parser")
    assert "가상 테스트 데이터" in soup.get_text()
    assert "실제 고객 SEO 미검증" in soup.get_text()
    assert "영업 담당자" in soup.get_text() and "기술 담당자" in soup.get_text()
    assert "directives" in json.dumps(result)


@pytest.mark.parametrize("consent", [False, None, "true", 1])
def test_no_consent_means_zero_requests(tmp_path, consent):
    folder = project(tmp_path, consent=consent)
    result, calls = audit(folder)
    assert calls == [] and result["requests"] == []
    assert result["status"] == "BLOCKED"
    assert check(result["findings"], "scope.consent")["result"] == "NOT_VERIFIED"


def test_unknown_cms_still_audits_and_default_no_discovery(tmp_path):
    folder = project(tmp_path)
    result, calls = audit(folder)
    assert result["environment_reference"]["refreshed"] is False
    assert "/doctors" not in calls
    assert result["summary"]["analyzed_pages"] == 1


@pytest.mark.parametrize("site", [None, "bad-url", "http://127.0.0.1/", "file:///x"])
def test_invalid_or_missing_project_site_url_is_not_requested(tmp_path, site):
    result, calls = audit(project(tmp_path, site=site, targets=[]))
    assert calls == [] and result["status"] == "BLOCKED"
    assert check(result["findings"], "scope.url")["result"] == "NOT_VERIFIED"


def test_intentional_noindex_http_exclusion_not_high_error(tmp_path):
    result, _ = audit(project(tmp_path), {"/robots.txt": (404, "", {}), "/": (403, "private", {"content-type": "text/html"})}, AuditOptions(indexing_goal="noindex"))
    assert check(result["findings"], "http.response")["result"] == "WARNING"
    assert check(result["findings"], "http.response")["severity"] == "LOW"


def test_nofollow_does_not_add_discovered_requests(tmp_path):
    html = HTML.replace("</head>", '<meta name="robots" content="nofollow"></head>')
    result, calls = audit(project(tmp_path), {"/robots.txt": (404, "", {}), "/": (200, html, {"content-type": "text/html"})}, AuditOptions(crawl=True))
    assert calls == ["/robots.txt", "/"]
    assert result["pages"][0]["observations"]["internal_links"] == [SITE + "doctors"]


def test_approved_crawl_limit_and_dangerous_links_not_requested(tmp_path):
    folder = project(tmp_path)
    routes = {"/robots.txt": (200, "User-agent: *\nAllow: /", {"content-type": "text/plain"}),
              "/": (200, HTML + '<a href="/wp-admin">admin</a><a href="https://evil.example/">external</a><a href="/?page=2">infinite</a>', {"content-type": "text/html"}),
              "/doctors": (200, HTML, {"content-type": "text/html"})}
    result, calls = audit(folder, routes, AuditOptions(max_pages=2, crawl=True))
    assert calls == ["/robots.txt", "/", "/doctors"]
    assert result["summary"]["analyzed_pages"] == 2
    assert any(f["id"] == "title.cross_page_duplicate" and f["result"] == "WARNING" for f in result["findings"])
    limited, calls = audit(folder, routes, AuditOptions(max_pages=1, crawl=True))
    assert calls == ["/robots.txt", "/"] and limited["scope"]["remaining_url_count"] == 1
    assert list((folder / "history").glob("seo-*/*"))


def test_explicit_target_priority_and_scope_exclusion(tmp_path):
    folder = project(tmp_path, targets=[SITE + "doctors", SITE + "login", "https://other.example/"])
    result, calls = audit(folder, {"/robots.txt": (404, "", {}), "/doctors": (200, HTML, {"content-type": "text/html"})})
    assert calls == ["/robots.txt", "/doctors"]
    assert result["summary"]["failed_pages"] == 2


@pytest.mark.parametrize("body,ctype,status", [("User-agent: *\nDisallow: /", "text/plain", 200), ("down", "text/plain", 503), ("blocked", "text/plain", 403), ("<html>not robots</html>", "text/html", 200)])
def test_robots_blocks_or_unknown_prevent_page_requests(tmp_path, body, ctype, status):
    result, calls = audit(project(tmp_path), {"/robots.txt": (status, body, {"content-type": ctype})})
    assert calls == ["/robots.txt"]
    assert result["pages"][0]["error"]["code"] == "ROBOTS_BLOCKED"
    assert not any(f["id"] == "title.declaration" for f in result["findings"])


def test_yeti_disallow_is_reported_without_impersonating_yeti(tmp_path):
    routes = {"/robots.txt": (200, "User-agent: *\nAllow: /\nUser-agent: Yeti\nDisallow: /", {"content-type": "text/plain"}), "/": (200, HTML, {"content-type": "text/html"})}
    result, calls = audit(project(tmp_path), routes, AuditOptions(indexing_goal="index"))
    assert calls == ["/robots.txt", "/"]
    assert check(result["findings"], "robots.access")["result"] == "ISSUE"


def test_redirect_target_path_blocked_and_http_errors_distinct(tmp_path):
    folder = project(tmp_path, targets=[SITE, SITE + "error"])
    result, calls = audit(folder, {"/robots.txt": (404, "", {}), "/": (302, "", {"location": "/wp-admin/"}), "/error": (403, "no", {"content-type": "text/html"})})
    assert calls == ["/robots.txt", "/", "/error"]
    assert result["pages"][0]["error"]["code"] == "EXCLUDED_PATH"
    assert result["pages"][1]["state"] == "HTTP_ERROR"
    assert result["pages"][1]["http"]["status_code"] == 403
    assert not any(f["id"] == "title.declaration" for f in result["findings"])


def test_dns_rebinding_during_page_redirect_blocked(tmp_path, monkeypatch):
    count = 0
    def dns(*args, **kwargs):
        nonlocal count
        count += 1
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1" if count >= 3 else "93.184.216.34", 443))]
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    result, calls = audit(project(tmp_path), {"/robots.txt": (404, "", {}), "/": (302, "", {"location": "/next"})})
    assert calls == ["/robots.txt", "/"]
    assert result["pages"][0]["error"]["code"] == "UNSAFE_DESTINATION"


def test_sitemap_approval_validity_and_actual_status_without_extra_pages(tmp_path):
    routes = {"/robots.txt": (200, 'User-agent: *\nAllow: /\nSitemap: ' + SITE + 'map.xml', {"content-type": "text/plain"}),
              "/": (200, HTML, {"content-type": "text/html"}), "/map.xml": (200, xml([SITE, SITE + "unapproved", "https://other.example/"]), {"content-type": "application/xml"})}
    folder = project(tmp_path)
    result, calls = audit(folder, routes)
    assert calls == ["/robots.txt", "/"] and not result["sitemaps"]
    result, calls = audit(folder, routes, AuditOptions(check_sitemaps=True))
    assert calls == ["/robots.txt", "/", "/map.xml"]
    assert result["sitemaps"][0]["unchecked_url_count"] == 2
    assert check(result["findings"], "sitemap.responses")["result"] == "NOT_VERIFIED"
    routes["/map.xml"] = (200, "<invalid", {"content-type": "application/xml"})
    result, _ = audit(folder, routes, AuditOptions(check_sitemaps=True))
    assert result["sitemaps"][0]["state"] == "INVALID"


def test_sitemap_index_request_cap_and_robots_for_every_resource(tmp_path):
    routes = {"/robots.txt": (200, 'User-agent: *\nDisallow: /denied.xml\nSitemap: ' + SITE + 'index.xml', {"content-type": "text/plain"}),
              "/": (200, HTML, {"content-type": "text/html"}), "/index.xml": (200, xml([SITE + p for p in ["denied.xml", "a.xml", "b.xml"]], "sitemapindex"), {"content-type": "application/xml"}),
              "/a.xml": (200, xml([SITE]), {"content-type": "application/xml"})}
    result, calls = audit(project(tmp_path), routes, AuditOptions(check_sitemaps=True))
    assert calls == ["/robots.txt", "/", "/index.xml", "/a.xml"]
    assert len(result["sitemaps"]) == 3
    assert result["sitemaps"][1]["state"] == "NOT_VERIFIED"
    assert check(result["findings"], "sitemap.limit")["result"] == "NOT_VERIFIED"


def test_sitemap_non_2xx_and_page_status_relation(tmp_path):
    routes = {"/robots.txt": (200, 'User-agent: *\nSitemap: ' + SITE + 'map.xml', {"content-type": "text/plain"}),
              "/": (404, "missing", {"content-type": "text/html"}), "/map.xml": (200, xml([SITE]), {"content-type": "application/xml"})}
    result, _ = audit(project(tmp_path), routes, AuditOptions(check_sitemaps=True))
    assert check(result["findings"], "sitemap.responses")["result"] == "WARNING"


def test_request_interval_and_crawl_delay_apply_to_each_get(tmp_path):
    delays = []
    routes = {"/robots.txt": (200, 'User-agent: *\nCrawl-delay: 2', {"content-type": "text/plain"}), "/": (302, "", {"location": "/next"}), "/next": (200, HTML, {"content-type": "text/html"})}
    calls = []
    audit_project(project(tmp_path), transport=mock(routes, calls), sleeper=delays.append, clock=lambda: 0, now=NOW)
    assert delays == [2, 2] and len(calls) == 3


@pytest.mark.parametrize("status", [429, 503])
def test_server_backoff_stops_remaining_approved_requests(tmp_path, status):
    result, calls = audit(project(tmp_path, targets=[SITE, SITE + "doctors"]), {"/robots.txt": (404, "", {}), "/": (status, "backoff", {"content-type": "text/html"})})
    assert calls == ["/robots.txt", "/"]
    assert result["pages"][0]["http"]["status_code"] == status
    assert result["pages"][1]["error"]["code"] == "SERVER_BACKOFF"


def test_invalid_output_path_rejected_before_http(tmp_path):
    folder = project(tmp_path)
    (folder / "seo-report.html").mkdir()
    with pytest.raises(IntakeError):
        audit(folder)


def test_response_size_timeout_and_non_html_recorded(tmp_path):
    folder = project(tmp_path)
    result, _ = audit(folder, {"/robots.txt": (404, "", {}), "/": (200, HTML * 3, {"content-type": "text/html"})}, AuditOptions(max_bytes=1024))
    assert result["pages"][0]["error"]["code"] == "BODY_TOO_LARGE"
    calls = []
    def timeout(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        raise httpx.ReadTimeout("timeout")
    result = audit_project(folder, transport=httpx.MockTransport(timeout), sleeper=lambda _: None, now=NOW)
    assert result["pages"][0]["error"]["code"] == "TIMEOUT"
    result, _ = audit(folder, {"/robots.txt": (404, "", {}), "/": (200, "document", {"content-type": "application/pdf"})})
    assert result["pages"][0]["state"] == "NON_HTML"
    assert not any(f["id"] == "title.declaration" for f in result["findings"])


def test_xss_secrets_and_offline_report_regeneration(tmp_path, monkeypatch):
    folder = project(tmp_path)
    evil = HTML.replace("가상 병원 진료 안내", '&lt;img src=x onerror=alert(1)&gt; user@example.com 010-1234-5678 password=TOPSECRET')
    result, _ = audit(folder, {"/robots.txt": (404, "", {}), "/": (200, evil, {"content-type": "text/html; charset=utf-8", "set-cookie": "private=COOKIESECRET"})})
    for name in ("seo-audit.json", "seo-report.html"):
        raw = (folder / name).read_text(encoding="utf-8")
        assert all(secret not in raw for secret in ("TOPSECRET", "COOKIESECRET", "user@example.com", "010-1234-5678"))
    html = (folder / "seo-report.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert not soup.select("script, img, iframe, [onerror], [onclick]")
    assert "default-src 'none'" in soup.find("meta", {"http-equiv": "Content-Security-Policy"})["content"]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("Offline report used DNS"))
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: pytest.fail("Offline report used HTTP"))
    raw = (folder / "seo-audit.json").read_bytes()
    assert regenerate_report(folder) == result
    assert (folder / "seo-audit.json").read_bytes() == raw
    assert cli.main(["project", "audit", str(folder), "--report-only"]) == 0


@pytest.mark.parametrize("options", [AuditOptions(max_pages=0), AuditOptions(max_pages=101), AuditOptions(interval=0), AuditOptions(interval=float("nan")), AuditOptions(timeout=11), AuditOptions(max_bytes=1)])
def test_invalid_options_no_requests(tmp_path, options):
    with pytest.raises(IntakeError):
        audit_project(project(tmp_path), options=options, transport=httpx.MockTransport(lambda r: pytest.fail("No HTTP")))


def test_real_cli_consent_block_and_offline_report(tmp_path):
    folder = project(tmp_path, consent=False)
    command = [sys.executable, "-m", "environment_detector", "project", "audit", str(folder)]
    run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1 and json.loads(run.stdout)["request_count"] == 0
    run = subprocess.run(command + ["--report-only"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1 and json.loads(run.stdout)["status"] == "BLOCKED"
    assert cli.main(["project", "audit", str(folder), "--interval", "0"]) == 1


def test_invalid_stored_audit_json_is_controlled_cli_error(tmp_path):
    folder = project(tmp_path, consent=False)
    audit(folder)
    path = folder / "seo-audit.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["summary"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["project", "audit", str(folder), "--report-only"]) == 1


def test_synthetic_intake_consent_cannot_authorize_real_http(tmp_path, monkeypatch):
    folder = project(tmp_path)
    path = folder / "project.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata["data_origin"] = "SYNTHETIC_TEST_FIXTURE"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("Synthetic consent must not authorize HTTP"))
    result = audit_project(folder)
    assert result["requests"] == [] and result["status"] == "BLOCKED"
    assert result["data_origin"] == "SYNTHETIC_TEST_FIXTURE_NOT_REQUESTED"
    assert check(result["findings"], "scope.synthetic")["result"] == "NOT_VERIFIED"
