import json
from pathlib import Path
import re
import socket
import subprocess

from bs4 import BeautifulSoup
import httpx
import pytest

from scripts import step1_2_collect as collect
from scripts import step1_2_report as report

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"


@pytest.fixture
def experiment(tmp_path):
    # Fixed target keys select historical REVIEWS; the fabricated records are not measurements.
    snapshot = json.loads((FIXTURES / "step1_2/snapshot.json").read_text(encoding="utf-8"))
    (tmp_path / "detector").mkdir()
    (tmp_path / "projectdiscovery").mkdir()
    for target in snapshot["measurements"]["targets"]:
        (tmp_path / "detector" / (target["name"] + ".json")).write_bytes(
            (FIXTURES / "step1" / (target["name"] + ".json")).read_bytes())
    (tmp_path / "measurements.json").write_text(json.dumps(snapshot["measurements"]), encoding="utf-8")
    (tmp_path / "projectdiscovery/results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in snapshot["projectdiscovery"]), encoding="utf-8")
    return tmp_path


def test_fixed_scope_and_passive_command():
    assert {url for _, url in collect.TARGETS} == {
        "https://www.nasa.gov/", "https://gilnmi.imweb.me/", "https://ecudemo159670.cafe24.com/",
        "https://nextjs.org/", "https://example.com/",
    }
    command = collect.pd_command("https://example.com/", ("104.20.23.154",), Path("empty.yaml"))
    assert Path(command[0]).name == "pd-httpx.exe"
    for flag, value in (("-threads", "1"), ("-rate-limit", "1"), ("-retries", "0"),
                        ("-x", "GET"), ("-protocol", "http11"), ("-allow", "104.20.23.154"),
                        ("-response-size-to-read", "2097152"), ("-exclude", "private-ips")):
        assert command[command.index(flag) + 1] == value
    assert {"-tech-detect", "-server", "-cdn", "-status-code", "-json", "-no-fallback-scheme", "-disable-update-check"} <= set(command)
    assert not {"-ports", "-path", "-follow-redirects", "-follow-host-redirects", "-favicon", "-screenshot", "-tls-probe", "-csp-probe", "-pipeline", "-http2", "-dashboard", "-pdu", "-probe-all-ips"} & set(command)


@pytest.mark.parametrize("result,external,expected", [
    (None, True, "출력 없음"),
    ({"failed": True}, True, "접근 실패"),
    ({"error": "timeout"}, True, "접근 실패"),
    ({"status_code": 403}, True, "HTTP 403"),
    ({"status_code": 200, "tech": []}, True, "HTTP 200 · 접근 성공"),
    ({}, True, "HTTP 상태 미확인"),
    ({"status": "error", "errors": [{"code": "DNS_ERROR"}]}, False, "분석 실패"),
    ({"status": "error", "errors": [{"code": "UNSUPPORTED_ENCODING"}]}, False, "분석 실패"),
    ({"status": "ok", "http": {"status_code": 200}}, False, "HTTP 200 · 접근 성공"),
])
def test_transport_and_identification_failures_are_distinct(result, external, expected):
    assert report.access_state(result, external).startswith(expected)


def test_five_target_synthetic_snapshot_preserves_unknown_and_unsupported_inferences(experiment):
    data = report.load_comparison(experiment)
    assert data["decision"] == "OPTIONAL"
    rows = {r["name"]: r for r in data["rows"]}
    assert len(rows) == 5
    assert all(r["pd_access"] == "HTTP 200 · 접근 성공" for r in rows.values())
    assert "PHP" in rows["wordpress_nasa"]["pd_tech"]
    assert "MySQL" in rows["wordpress_nasa"]["pd_tech"]
    assert rows["wordpress_nasa"]["own_technologies"]["backend"][0]["name"] == "UNKNOWN"
    assert "정답·누락 목록에서 제외" in rows["wordpress_nasa"]["review"]["limits"]
    assert "Next.js" not in rows["nextjs_official"]["pd_tech"]
    assert rows["nextjs_official"]["own_technologies"]["frontend"][0]["name"] == "Next.js"
    assert "Cloudflare" in rows["cafe24_demo"]["pd_tech"]
    assert rows["cafe24_demo"]["pd_cdn"] == "UNKNOWN"


def test_render_offline_with_no_site_requests(experiment, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline comparison renderer attempted networking or subprocess execution")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    assert report.main(["--folder", str(experiment)]) == 0
    html = (experiment / "comparison.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert len(soup.select("table tbody tr")) == 5
    assert "OPTIONAL" in soup.get_text()
    assert not soup.find(["script", "img", "link", "iframe", "form"])
    assert len(soup.select("details")) == 6


def test_html_does_not_execute_external_tech_names(experiment):
    data = report.load_comparison(experiment)
    data["rows"][0]["pd_tech"] = ['<img src=x onerror="alert(1)">']
    html = report.render_comparison(data)
    assert "&lt;img" in html
    assert not BeautifulSoup(html, "html.parser").find("img")


def test_missing_external_output_is_not_a_technology_miss(experiment):
    (experiment / "projectdiscovery/results.jsonl").write_text("", encoding="utf-8")
    data = report.load_comparison(experiment)
    assert all(r["pd_access"].startswith("출력 없음") for r in data["rows"])
    assert all(r["review"]["missed"] == "판정 보류" for r in data["rows"])
    assert data["decision"] == "판정 보류"


def test_hash_chunk_collision_is_not_p5_usage_proof():
    # The version annotation is removed from the upstream v0.2.96 scriptSrc rule.
    # This checks the observed ambiguity offline; no bundle/library is requested.
    upstream_rule = r"(?:((?:\d+\.)+\d+)\/(?:addons\/)?)?p5(?:\.sound)?(?:\.dom)?(?:\.min)?\.js"
    assert re.search(upstream_rule, "/_next/static/immutable/chunks/0q93co9tqv6p5.js")
    assert not re.search(upstream_rule, "/_next/static/immutable/chunks/0q93co9tqv6p6.js")
