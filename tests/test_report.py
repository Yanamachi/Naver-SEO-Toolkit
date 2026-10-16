from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from bs4 import BeautifulSoup
import httpx
import pytest

from environment_detector import cli
from environment_detector.redact import MASK, mask_text, redact
from environment_detector.report import (
    Entry, assessment, load_entries, render_report, result_state, terminal_summary,
)

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic" / "step1"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Report must never perform HTTP, DNS or site detection")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)
    monkeypatch.setattr(cli, "fetch_page", forbidden)


@pytest.fixture
def result():
    return json.loads((FIXTURES / "wordpress_nasa.json").read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_review_seven_synthetic_scenarios():
    entries = load_entries(FIXTURES)
    assert len(entries) == 7
    by_file = {e.filename: e for e in entries}
    assert by_file["blocked-smoke.json"].state == "blocked"
    assert by_file["customer.json"].state == "unknown"
    assert by_file["unknown_example.json"].state == "unknown"
    for filename, category, label, count in [
        ("imweb_gilnmi.json", "cms", "후보 · 미확정", 5),
        ("cafe24_demo.json", "cms", "후보 · 미확정", 9),
        ("nextjs_official.json", "frontend", "빌드 자원 확인", 10),
        ("wordpress_nasa.json", "cms", "명시 표기 확인", 10),
    ]:
        item = by_file[filename].data["technologies"][category][0]
        assert assessment(category, item)[0] == label
        assert len(item["evidence"]) == count
    imweb = by_file["imweb_gilnmi.json"].data["technologies"]
    assert imweb["server"][0]["name"] == "CloudFront"
    assert imweb["cdn"][0]["name"] == "UNKNOWN"


def test_report_cli_offline_aggregates_without_modifying_input(tmp_path, capsys):
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FIXTURES.glob("*.json")}
    output = tmp_path / "nested" / "report.html"
    assert cli.main(["report", str(FIXTURES), "-o", str(output)]) == 0
    summary = capsys.readouterr().out
    assert "총 7개 JSON" in summary
    assert "보안 차단 1" in summary and "기술 미확인 2" in summary
    assert "UNSAFE_DESTINATION" in summary
    soup = BeautifulSoup(output.read_text(encoding="utf-8"), "html.parser")
    assert len(soup.select("section[id^=result-]")) == 7
    assert len(soup.select('table[aria-label="파일별 종합 비교"] tbody tr')) == 7
    assert len(soup.select(".technology")) == 35
    assert "원본 서버: UNKNOWN" in soup.get_text()
    assert len(soup.select("details table tbody tr")) == 42
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FIXTURES.glob("*.json")}


def test_all_recorded_evidence_is_available_in_details():
    entries = load_entries(FIXTURES)
    soup = BeautifulSoup(render_report(entries), "html.parser")
    for entry, section in zip(entries, soup.select("section[id^=result-]")):
        if entry.state == "input_error":
            continue
        expected = sum(len(item["evidence"]) for items in entry.data["technologies"].values() for item in items)
        assert len(section.select("details table tbody tr")) == expected
    assert not soup.find(["script", "img", "iframe", "link", "form", "object", "embed"])
    assert all(a["href"].startswith("#result-") for a in soup.find_all("a"))
    assert "default-src 'none'" in soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"})["content"]


@pytest.mark.parametrize("name", ["Imweb", "Cafe24"])
def test_candidate_not_promoted_by_high_confidence_or_generator(name):
    item = {"name": name, "confidence": 1.0, "evidence": [{"rule": "invented_generator"}] * 30}
    assert assessment("cms", item)[0] == "후보 · 미확정"


@pytest.mark.parametrize("server", ["nginx", "CloudFront", "cloudflare", "Vercel"])
def test_server_never_promoted_to_origin_or_cdn(result, server):
    result["technologies"]["server"][0]["name"] = server
    rendered = render_report([Entry("test.json", result, "ok")])
    assert "HTTP 응답 서버 (공개 표기)" in rendered
    assert "원본 서버: <strong>UNKNOWN</strong>" in rendered
    assert "자체 개발 여부: <strong>UNKNOWN</strong>" in rendered
    assert result["technologies"]["cdn"][0]["name"] == "UNKNOWN"


@pytest.mark.parametrize("code,state", [
    ("UNSAFE_URL", "blocked"), ("UNSAFE_DESTINATION", "blocked"),
    ("REDIRECT_SCOPE", "blocked"), ("UNSAFE_REDIRECT", "blocked"),
    ("DNS_ERROR", "error"), ("TIMEOUT", "error"), ("HTTP_ERROR", "error"),
    ("OUTPUT_ERROR", "error"), ("UNSUPPORTED_ENCODING", "error"),
])
def test_error_states_are_separate_from_unknown(result, code, state):
    result["status"] = "error"
    result["errors"] = [{"code": code, "message": "failed"}]
    assert result_state(result) == state


@pytest.mark.parametrize("text,secret", [
    ("https://user:URLSECRET@example.com/path", "URLSECRET"),
    ("//user:RELSECRET@example.com/path", "RELSECRET"),
    ("ftp://user:FTPSECRET@example.com/path", "FTPSECRET"),
    ("/asset.js?unexpected=QUERYSECRET&version=1", "QUERYSECRET"),
    ("https://example.com/path#FRAGMENTSECRET", "FRAGMENTSECRET"),
    ("Bearer BEARERSECRET", "BEARERSECRET"),
    ("Basic BASICSECRET", "BASICSECRET"),
    ("password=PASSWORDSECRET", "PASSWORDSECRET"),
    ("Cookie: a=COOKIESECRET; b=2", "COOKIESECRET"),
    ("X-Api-Key: APISECRET", "APISECRET"),
])
def test_masking_free_text(text, secret):
    masked = mask_text(text)
    assert secret not in masked
    assert MASK in masked


def test_sensitive_fields_masked_recursively():
    data = {"http": {"headers": {"set-cookie": "COOKIESECRET", "Authorization": "AUTHSECRET"}},
            "password": "PASSWORDSECRET", "nested": [{"api_key": "APISECRET"}],
            "evidence": [{"source": "http.header.authorization", "value": "VALUESECRET"}]}
    text = json.dumps(redact(data))
    assert all(secret not in text for secret in ("COOKIESECRET", "AUTHSECRET", "PASSWORDSECRET", "APISECRET", "VALUESECRET"))
    assert data["password"] == "PASSWORDSECRET"


def test_terminal_control_characters_removed():
    masked = mask_text("safe\x1b[31m\x9b31m\u202e\x07")
    assert all(control not in masked for control in ("\x1b", "\x9b", "\u202e", "\x07"))


@pytest.mark.parametrize("text", [
    "새 공개 영역 분석이 필요할 경우 해당 홈페이지의 비침투적 분석에 동의하시나요? 계정·비밀번호는 보내지 마세요.",
    "자료가 있나요? 파일을 전달해 주세요.", "어떤 화면인가요?무엇을 원하시나요?",
    "확인할까요?", "#1 문의 항목", "C# 개발 및 #네이버 태그", "의료진 / 진료과목 / 제품",
])
def test_normal_prose_questions_and_hashtags_are_not_url_secrets(text):
    assert mask_text(text) == text
    assert mask_text(mask_text(text)) == text


@pytest.mark.parametrize("text,secret", [
    ("참고: https://example.com/?BARESECRET", "BARESECRET"),
    ("https://example.com/path#FRAGMENTSECRET", "FRAGMENTSECRET"),
    ("//example.com/a?x=QUERYSECRET", "QUERYSECRET"),
    ("../image.png?QUERYSECRET", "QUERYSECRET"),
    ("image.png#FRAGMENTSECRET", "FRAGMENTSECRET"),
    ("?odd_name=QUERYSECRET", "QUERYSECRET"),
])
def test_url_context_redaction_preserved(text, secret):
    assert secret not in mask_text(text)
    assert MASK in mask_text(text)


def test_synthetic_detector_report_warns_without_rewriting_json(result):
    result["data_origin"] = "SYNTHETIC_TEST_FIXTURE"
    before = deepcopy(result)
    html = render_report([Entry("fixture.json", result, "ok")])
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one(".synthetic-warning")
    assert "가상" in soup.select_one(".state").get_text()
    assert all("실제 평가에 사용하지 않음" in e.get_text() for e in soup.select(".score"))
    assert "명시 표기 확인" not in " ".join(e.get_text() for e in soup.select(".technology"))
    assert result == before
    assert result["technologies"]["cms"][0]["confidence"] == 0.95
    terminal = terminal_summary([Entry("fixture.json", result, "ok")])
    assert "가상 테스트 데이터" in terminal
    assert "명시 표기 확인" not in terminal


def test_all_output_fields_escaped_and_masked(result, tmp_path, capsys):
    attack = '<img src=x onerror="alert(1)"><script>alert(1)</script>'
    result["request_url"] = "https://user:URLSECRET@example.com/?x=QUERYSECRET#FRAGMENTSECRET"
    result["final_url"] = attack
    result["errors"] = [{"code": attack, "message": "password=ERRORSECRET"}]
    result["technologies"]["cms"][0]["name"] = attack
    evidence = result["technologies"]["cms"][0]["evidence"][0]
    evidence.update(value=attack, meaning=attack, reference='javascript:alert("REFSECRET")?x=QUERYSECRET')
    result["http"]["headers"]["authorization"] = "AUTHSECRET"
    result["extra"] = {"secret": "EXTRASECRET"}
    source = tmp_path / "input.json"
    write_json(source, result)
    output = tmp_path / "out.html"
    assert cli.main(["report", str(source), "-o", str(output)]) == 0
    html = output.read_text(encoding="utf-8")
    terminal = capsys.readouterr().out
    assert all(s not in html + terminal for s in ("URLSECRET", "QUERYSECRET", "FRAGMENTSECRET", "ERRORSECRET", "AUTHSECRET", "EXTRASECRET"))
    soup = BeautifulSoup(html, "html.parser")
    assert not soup.find(["script", "img"])
    assert not soup.select("[onerror]")
    assert attack in soup.get_text()
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("content", [
    b"not json", b"[]", b"null", b"{}", b"\xff", b'{"schema_version":"2.0"}',
])
def test_malformed_inputs_are_cards_not_crashes(content, tmp_path):
    (tmp_path / "bad.json").write_bytes(content)
    entries = load_entries(tmp_path)
    assert entries[0].state == "input_error"
    assert "JSON 입력 오류" in render_report(entries)


@pytest.mark.parametrize("mutation", ["score", "evidence", "errors", "name", "categories"])
def test_malformed_schema(result, mutation, tmp_path):
    item = result["technologies"]["cms"][0]
    if mutation == "score":
        item["confidence"] = float("nan")
    elif mutation == "evidence":
        item["evidence"] = ["broken"]
    elif mutation == "errors":
        result["errors"] = [None]
    elif mutation == "name":
        item["name"] = []
    else:
        result["technologies"] = {}
    write_json(tmp_path / "bad.json", result)
    assert load_entries(tmp_path)[0].state == "input_error"


def test_mixed_valid_invalid_and_default_output(result, tmp_path, capsys):
    write_json(tmp_path / "valid.json", result)
    (tmp_path / "bad.json").write_text("broken", encoding="utf-8")
    (tmp_path / "archive.zip").write_bytes(b"not read")
    (tmp_path / "folder.json").mkdir()
    assert cli.main(["report", str(tmp_path)]) == 1
    assert len(BeautifulSoup((tmp_path / "report.html").read_text(encoding="utf-8"), "html.parser").select("section[id^=result-]")) == 2
    assert "JSON 입력 오류 1" in capsys.readouterr().out


def test_oversize_file_is_rejected(tmp_path):
    (tmp_path / "large.json").write_bytes(b" " * (5 * 1024 * 1024 + 1))
    assert load_entries(tmp_path)[0].state == "input_error"


def test_cannot_overwrite_json(result, tmp_path, capsys):
    source = tmp_path / "original.json"
    write_json(source, result)
    before = source.read_bytes()
    assert cli.main(["report", str(source), "-o", str(source)]) == 1
    assert source.read_bytes() == before
    assert capsys.readouterr().err


def test_missing_empty_inputs_and_bad_output(tmp_path, capsys):
    assert cli.main(["report", str(tmp_path / "missing")]) == 1
    assert cli.main(["report", str(tmp_path)]) == 1
    assert cli.main(["report", str(FIXTURES), "-o", str(tmp_path / "x.json")]) == 1
    blocked_parent = tmp_path / "file"
    blocked_parent.write_text("x", encoding="utf-8")
    assert cli.main(["report", str(FIXTURES), "-o", str(blocked_parent / "x.html")]) == 1
    assert capsys.readouterr().err


def test_legacy_scan_summary_is_opt_in_stderr(legacy_environment, monkeypatch, tmp_path, capsys):
    # Keep the unmarked schema CLI label contract independently of synthetic warnings.
    result = legacy_environment
    monkeypatch.setattr(cli, "run", lambda url: deepcopy(result))
    output = tmp_path / "scan.json"
    assert cli.main(["https://example.com", "-o", str(output)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    assert captured.err == ""
    assert cli.main(["https://example.com", "-o", str(output), "--summary"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result
    assert "WordPress (명시 표기 확인)" in captured.err
    assert json.loads(output.read_text(encoding="utf-8")) == result


def test_subprocess_entrypoint_report_and_original_blocked_cli(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    command = subprocess.run([sys.executable, "-m", "environment_detector", "report", str(FIXTURES),
                              "-o", str(tmp_path / "report.html")], capture_output=True, text=True, encoding="utf-8", env=env)
    assert command.returncode == 0, command.stderr
    assert "총 7개 JSON" in command.stdout
    command = subprocess.run([sys.executable, "-m", "environment_detector", "http://127.0.0.1",
                              "-o", str(tmp_path / "blocked.json"), "--summary"],
                             capture_output=True, text=True, encoding="utf-8", env=env)
    assert command.returncode == 1
    assert json.loads(command.stdout)["errors"][0]["code"] == "UNSAFE_DESTINATION"
    assert "보안 차단" in command.stderr
