"""Provenance and independent reproduction; no historical raw results are read."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from bs4 import BeautifulSoup
import pytest

from environment_detector.detect import analyze
from environment_detector.projects import create_project
from environment_detector.report import load_entries, render_report, validate_result
from environment_detector.workbench import build_workbench
from scripts import step1_2_collect as collect
from scripts import step1_2_report as comparison

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"
ORIGIN = "SYNTHETIC_TEST_FIXTURE"
NAMES = {"blocked-smoke", "cafe24_demo", "customer", "imweb_gilnmi",
         "nextjs_official", "unknown_example", "wordpress_nasa"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_exact_inventory_and_explicit_nonmeasurement_origin():
    paths = sorted(FIXTURES.rglob("*.json"))
    assert {p.relative_to(FIXTURES).as_posix() for p in paths} == {
        *("step1/" + name + ".json" for name in NAMES), "step1_2/snapshot.json"}
    for path in paths:
        data = read(path)
        assert data["data_origin"] == ORIGIN
        assert data["fixture_purpose"]
        text = path.read_text(encoding="utf-8")
        assert "C:\\Users\\" not in text and "/Users/" not in text
        if path.parent.name == "step1":
            assert data["analyzed_at"] is None
            assert set(data["fixture_input"]) == {"headers", "html"}
            assert "?ver=" not in text and "WordPress 7." not in text
    snapshot = read(FIXTURES / "step1_2/snapshot.json")
    measurements = snapshot["measurements"]
    assert measurements["data_origin"] == ORIGIN
    assert measurements["pd_version"] == "SYNTHETIC_NOT_EXECUTED"
    assert measurements["started_at"] == measurements["finished_at"] == "SYNTHETIC_NOT_MEASURED"
    assert {(t["name"], t["url"]) for t in measurements["targets"]} == set(collect.TARGETS)
    assert all(t["detector_elapsed_seconds"] == t["pd_elapsed_seconds"] == 0
               for t in measurements["targets"])
    assert len(snapshot["projectdiscovery"]) == 5
    assert {r["input"] for r in snapshot["projectdiscovery"]} == {url for _, url in collect.TARGETS}
    assert all(r["data_origin"] == ORIGIN and set(r) == {"data_origin", "input", "status_code", "tech"}
               for r in snapshot["projectdiscovery"])


@pytest.mark.parametrize("name", sorted(NAMES))
def test_hand_authored_input_reproduces_the_saved_evidence(name):
    data = read(FIXTURES / "step1" / (name + ".json"))
    before = deepcopy(data)
    validate_result(data)
    expected = analyze(data["fixture_input"]["headers"], data["fixture_input"]["html"], data["request_url"])
    assert data["technologies"] == expected["technologies"]
    assert data["development_model"] == expected["development_model"]
    assert all(item["name"] == "UNKNOWN" for item in data["technologies"]["backend"])
    if name == "blocked-smoke":
        assert data["status"] == "error" and data["http"] is None
        assert [e["code"] for e in data["errors"]] == ["UNSAFE_DESTINATION"]
        assert data["fixture_input"] == {"headers": {}, "html": ""}
    else:
        assert data["status"] == "ok" and data["errors"] == []
        assert data["http"]["size_bytes"] == len(data["fixture_input"]["html"].encode())
    assert data == before


def test_synthetic_report_retains_all_evidence_and_warns_on_every_card():
    entries = load_entries(FIXTURES / "step1")
    assert len(entries) == 7
    assert [e.state for e in entries].count("blocked") == 1
    assert [e.state for e in entries].count("unknown") == 2
    soup = BeautifulSoup(render_report(entries), "html.parser")
    assert len(soup.select(".synthetic-warning")) == 1
    assert "가상 테스트 데이터 포함: 7개" in soup.select_one(".synthetic-warning").get_text()
    assert len(soup.select("details table tbody tr")) == 42
    assert all("가상" in s.get_text() for s in soup.select(".state"))
    assert all("실제 평가에 사용하지 않음" in s.get_text() for s in soup.select(".score"))


def test_isolated_fixture_tree_supports_reports_comparison_and_unverified_project(tmp_path):
    # Copy only the declared eight JSON files: the historical directories do not exist here.
    isolated = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, isolated, ignore=shutil.ignore_patterns("*.md", "__pycache__"))
    assert len(list(isolated.rglob("*.json"))) == 8
    assert not (isolated / "step1_2" / "measurements.json").exists()
    assert len(load_entries(isolated / "step1")) == 7
    snapshot = read(isolated / "step1_2/snapshot.json")
    experiment = tmp_path / "experiment"
    (experiment / "detector").mkdir(parents=True)
    (experiment / "projectdiscovery").mkdir()
    dump(experiment / "measurements.json", snapshot["measurements"])
    for target in snapshot["measurements"]["targets"]:
        shutil.copyfile(isolated / "step1" / (target["name"] + ".json"),
                        experiment / "detector" / (target["name"] + ".json"))
    (experiment / "projectdiscovery/results.jsonl").write_text(
        "\n".join(json.dumps(row) for row in snapshot["projectdiscovery"]), encoding="utf-8")
    result = comparison.load_comparison(experiment)
    assert result["decision"] == "OPTIONAL" and len(result["rows"]) == 5
    assert result["pd_version"] == "SYNTHETIC_NOT_EXECUTED"
    assert all(row["own_elapsed"] == row["pd_elapsed"] == 0 for row in result["rows"])

    site = "https://www.nasa.gov/"
    form = {"company_name": "합성 테스트", "industry": "테스트", "site_url": site,
            "reported_cms": "WordPress", "requested_services": ["seo"], "target_queries": ["테스트"],
            "target_page_urls": [site], "reference_result": {"urls": ["https://example.com/"], "device": "모바일"},
            "content_available": "yes", "modification_owner": "테스트 역할", "modification_route": "검토",
            "desired_schedule": "협의", "public_analysis_consent": True}
    source = tmp_path / "intake.json"
    dump(source, form)
    folder, _, review = create_project(source, environment_path=isolated / "step1/wordpress_nasa.json",
                                      projects_dir=tmp_path / "jobs",
                                      now=datetime(2001, 1, 1, tzinfo=timezone.utc))
    assert review["decision"] == "NEED_INFO" and review["analysis"]["synthetic"] is True
    assert review["environment_comparison"]["observed_cms"] == ["UNKNOWN"]
    assert any(q["code"] == "SYNTHETIC_ENVIRONMENT" for q in review["questions"])
    assert read(folder / "environment.json")["data_origin"] == ORIGIN
    model = build_workbench(folder, now=datetime(2001, 1, 1, tzinfo=timezone.utc))
    assert model["synthetic"]
    assert model["states"]["environment"][0] == "NOT_VERIFIED"
    assert model["states"]["review"][0] != "READY"
    assert model["states"]["seo"][0] == "NOT_STARTED"
