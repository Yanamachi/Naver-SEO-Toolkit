import json

from environment_detector import cli
from environment_detector.fetch import Page
from environment_detector.safety import DetectorError
import httpx


def test_json_stdout_file_and_header_redaction(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "fetch_page", lambda url: Page(
        url, 200, httpx.Headers({"content-type": "text/html", "server": "nginx",
                                "set-cookie": "session=secret", "x-secret": "secret"}),
        '<meta name="generator" content="WordPress">', [], 50,
    ))
    output = tmp_path / "nested" / "환경.json"
    assert cli.main(["https://example.com", "-o", str(output)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(output.read_text(encoding="utf-8"))
    assert printed["status"] == "ok"
    assert printed["technologies"]["cms"][0]["name"] == "WordPress"
    assert "secret" not in output.read_text(encoding="utf-8")


def test_blocked_url_writes_error_json(tmp_path, capsys):
    output = tmp_path / "error.json"
    assert cli.main(["http://127.0.0.1", "-o", str(output)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "UNSAFE_DESTINATION"
    assert result["technologies"]["cms"][0]["name"] == "UNKNOWN"
    assert json.loads(output.read_text(encoding="utf-8")) == result


def test_output_failure_is_json(monkeypatch, tmp_path, capsys):
    def fail(url):
        raise DetectorError("DNS_ERROR", "DNS resolution failed.")
    monkeypatch.setattr(cli, "fetch_page", fail)
    assert cli.main(["https://example.com", "-o", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert [error["code"] for error in result["errors"]] == ["DNS_ERROR", "OUTPUT_ERROR"]
    assert captured.err


def test_default_output_is_saved(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["file:///etc/passwd"]) == 1
    assert json.loads((tmp_path / "results/environment.json").read_text(encoding="utf-8")) == json.loads(capsys.readouterr().out)
