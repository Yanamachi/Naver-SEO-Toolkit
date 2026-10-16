from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from bs4 import BeautifulSoup
import httpx
import pytest

from environment_detector import cli, projects
from environment_detector.intake import IntakeError, available_screenshots, normalize, normalize_notes, private_copy
from environment_detector.pre_review import analysis_age, assess

NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Project workflow unexpectedly performed networking")
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(httpx, "Client", forbidden)


@pytest.fixture
def form():
    return {"company_name": "가상 고객", "industry": "가상 서비스", "site_url": "https://www.nasa.gov/",
            "reported_cms": None, "requested_services": ["SEO"], "target_queries": ["가상 검색어"],
            "reference_result": {"urls": ["https://example.com/"], "screenshots": [], "device": "모바일", "description": "목표 예시"},
            "content_type": None, "target_page_urls": ["https://www.nasa.gov/"],
            "content_available": "yes", "images_available": "yes", "content_usage_rights": "yes",
            "modification_owner": "고객 제작 부서", "modification_route": "제작 부서에 수정안 전달",
            "desired_schedule": "협의 가능", "additional_requests": "사전 견적 검토만", "public_analysis_consent": True}


@pytest.fixture
def environment(legacy_environment):
    # Exercise unmarked schema compatibility with a fixed test clock, not a site measurement.
    legacy_environment["analyzed_at"] = NOW.isoformat()
    return legacy_environment


def create(tmp_path, form, environment=None, **kwargs):
    source = dump(tmp_path / "request.json", form)
    if environment is not None:
        kwargs["environment_path"] = dump(tmp_path / "environment-source.json", environment)
    elif "reuse_dir" not in kwargs and not kwargs.get("analyze"):
        kwargs["reuse_dir"] = tmp_path / "no-cache"
    return projects.create_project(source, projects_dir=tmp_path / "jobs", now=NOW, **kwargs)


def unknown_environment(environment):
    result = deepcopy(environment)
    for category in result["technologies"]:
        result["technologies"][category] = [{"name": "UNKNOWN", "confidence": 0.0, "evidence": []}]
    return result


def test_ready_does_not_require_customer_cms_or_imply_deploy(tmp_path, form, environment):
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "READY"
    assert review["deployment_access"] == "NOT_VERIFIED"
    assert review["search_display_guaranteed"] is False
    assert review["questions"] == []
    assert read(folder / "intake.json")["request"]["reported_cms"] is None
    assert {"intake.json", "environment.json", "review.json", "questions.json", "project.json", "report.html", ".gitignore"} <= {p.name for p in folder.iterdir()}
    assert (folder / ".gitignore").read_text(encoding="utf-8") == "*\n"


def test_empty_form_is_accepted_with_questions(tmp_path):
    folder, _, review = create(tmp_path, {})
    assert review["decision"] == "NEED_INFO"
    assert any(q["field"] == "company_name" for q in review["questions"])
    assert read(folder / "environment.json")["status"] == "error"


@pytest.mark.parametrize("url", ["not-a-url", "file:///etc/passwd", "http://127.0.0.1", "http://169.254.169.254", "http://localhost", "https://user:URLSECRET@example.com", "https://example.com:8080", "https://example.com/?token=URLSECRET"])
def test_bad_or_private_url_never_requested(tmp_path, form, url, monkeypatch):
    form["site_url"] = url
    monkeypatch.setattr(cli, "run", lambda url: pytest.fail("Invalid URL must not be sent to Detector"))
    folder, _, review = create(tmp_path, form, analyze=True)
    assert review["decision"] == "NEED_INFO"
    assert read(folder / "environment.json")["errors"][0]["code"] == "INVALID_SITE_URL"
    assert "URLSECRET" not in (folder / "intake.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("consent", [None, False, "true", "false", 1, [], {}])
def test_explicit_true_is_required_for_live_request(tmp_path, form, consent, monkeypatch):
    form["public_analysis_consent"] = consent
    monkeypatch.setattr(cli, "run", lambda url: pytest.fail("No explicit boolean consent"))
    folder, _, review = create(tmp_path, form, analyze=True)
    assert review["decision"] == "NEED_INFO"
    assert read(folder / "environment.json")["errors"][0]["code"] == "CONSENT_REQUIRED"


def test_live_request_calls_existing_detector_once(tmp_path, form, environment, monkeypatch):
    calls = []
    def scan(url):
        calls.append(url)
        return environment
    monkeypatch.setattr(cli, "run", scan)
    folder, _, review = create(tmp_path, form, analyze=True)
    assert calls == [form["site_url"]]
    assert review["analysis"]["acquisition"] == "LIVE"
    assert read(folder / "environment.json")["schema_version"] == "1.0"


def test_source_reuse_no_consent_still_makes_no_request(tmp_path, form, environment, monkeypatch):
    form["public_analysis_consent"] = False
    monkeypatch.setattr(cli, "run", lambda url: pytest.fail("Reuse must remain offline"))
    source = dump(tmp_path / "source.json", environment)
    before = source.read_bytes()
    folder, _, review = projects.create_project(dump(tmp_path / "intake.json", form),
        environment_path=source, projects_dir=tmp_path / "jobs", now=NOW)
    assert source.read_bytes() == before
    assert review["analysis"]["acquisition"] == "REUSED"
    assert read(folder / "environment.json")["analyzed_at"] == environment["analyzed_at"]


def test_reuse_selects_newest_successful_same_url_not_newer_error(tmp_path, form, environment):
    cache = tmp_path / "cache"
    cache.mkdir()
    old = deepcopy(environment)
    old["analyzed_at"] = (NOW - timedelta(days=20)).isoformat()
    dump(cache / "old.json", old)
    new = deepcopy(environment)
    new["analyzed_at"] = (NOW - timedelta(days=1)).isoformat()
    dump(cache / "new.json", new)
    error = deepcopy(environment)
    error.update(status="error", analyzed_at=NOW.isoformat())
    error["errors"] = [{"code": "HTTP_ERROR", "message": "HTTP 403"}]
    dump(cache / "error.json", error)
    other = deepcopy(environment)
    other["request_url"] = "https://other.example.com/"
    dump(cache / "other.json", other)
    (cache / "broken.json").write_text("bad", encoding="utf-8")
    _, _, review = create(tmp_path, form, reuse_dir=cache)
    assert review["analysis"]["source_filename"] == "new.json"


def test_mismatched_cache_is_rejected_before_creating_project(tmp_path, form, environment):
    environment["request_url"] = "https://example.com/"
    with pytest.raises(IntakeError):
        create(tmp_path, form, environment)
    assert not (tmp_path / "jobs").exists()


def test_unknown_is_need_info_not_assumed_custom(tmp_path, form, environment):
    _, _, review = create(tmp_path, form, unknown_environment(environment))
    assert review["decision"] == "NEED_INFO"
    assert any(q["code"] == "ENVIRONMENT_UNKNOWN" for q in review["questions"])
    assert review["environment_comparison"]["customer_reported"] == "UNKNOWN"


def test_declared_custom_can_route_to_custom_quote_without_asserting_detection(tmp_path, form, environment):
    form["reported_cms"] = "자체 개발"
    folder, _, review = create(tmp_path, form, unknown_environment(environment))
    assert review["decision"] == "CUSTOM_QUOTE"
    assert review["environment_comparison"]["observed_cms"] == ["UNKNOWN"]
    assert read(folder / "intake.json")["request"]["reported_cms"] == "자체 개발"


def test_missing_information_precedes_custom_quote(tmp_path, form, environment):
    form.update(reported_cms="자체 개발", modification_owner=None)
    _, _, review = create(tmp_path, form, unknown_environment(environment))
    assert review["decision"] == "NEED_INFO"


@pytest.mark.parametrize("field", ["company_name", "industry", "site_url", "requested_services", "target_queries", "reference_result", "target_page_urls", "content_available", "modification_owner", "modification_route", "desired_schedule"])
def test_missing_quote_information_generates_specific_question(tmp_path, form, environment, field):
    form.pop(field)
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert any(q["field"] == field or q["field"].startswith(field + ".") for q in review["questions"])


@pytest.mark.parametrize("field", ["images_available", "content_usage_rights", "content_review_owner"])
def test_hospital_carousel_missing_assets_or_review_owner(tmp_path, form, environment, field):
    form = carousel(form)
    form.update(industry="의원", content_review_owner="고객 콘텐츠 검토 부서")
    form.pop(field)
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert any(q["field"] == field for q in review["questions"])


def test_explicit_complexity_record_can_route_unknown_to_custom_quote(tmp_path, form, environment):
    notes = dump(tmp_path / "notes.json", {"reviewer_role": "기술 검토 부서", "evidence": "고객 개발사가 다중 시스템 연동을 설명한 기록", "complex_environment": True})
    _, _, review = create(tmp_path, form, unknown_environment(environment), notes_path=notes)
    assert review["decision"] == "CUSTOM_QUOTE"
    assert review["environment_comparison"]["observed_cms"] == ["UNKNOWN"]


def test_supported_build_artifact_requires_custom_quote_not_backend_guess(tmp_path, form, environment):
    environment = unknown_environment(environment)
    environment["technologies"]["frontend"] = [{"name": "Next.js", "confidence": 0.8, "evidence": [{"rule": "next_assets", "source": "html.script.src", "value": "/_next/static/a.js", "meaning": "build resource", "reference": "https://nextjs.org/blog/next-7"}]}]
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "CUSTOM_QUOTE"
    assert read(folder / "environment.json")["technologies"]["backend"][0]["name"] == "UNKNOWN"


def test_error_snapshot_preserved_as_analysis_failure(tmp_path, form, environment):
    environment.update(status="error", http=None)
    environment["errors"] = [{"code": "TIMEOUT", "message": "HTTP request timed out"}]
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert read(folder / "environment.json")["errors"][0]["code"] == "TIMEOUT"
    assert any(q["code"] == "ENVIRONMENT_UNAVAILABLE" for q in review["questions"])


def test_corrupt_explicit_environment_rejected_without_project(tmp_path, form):
    bad = tmp_path / "bad-environment.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(IntakeError):
        projects.create_project(dump(tmp_path / "intake.json", form), projects_dir=tmp_path / "jobs", environment_path=bad)
    assert not (tmp_path / "jobs").exists()


def test_out_of_scope_is_based_on_explicit_service_not_free_text(tmp_path, form, environment):
    form["requested_services"] = ["결제 시스템 개발"]
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "OUT_OF_SCOPE"


def test_mixed_scope_requires_clarification(tmp_path, form, environment):
    form["requested_services"] = ["seo", "광고 운영"]
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert any(q["code"] == "MIXED_SCOPE" for q in review["questions"])


def test_cms_disagreement_never_overwrites_claim_or_evidence(tmp_path, form, environment):
    form["reported_cms"] = "아임웹"
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert review["environment_comparison"]["state"] == "DIFFERENT_CLUES"
    assert read(folder / "intake.json")["request"]["reported_cms"] == "아임웹"
    assert read(folder / "environment.json")["technologies"]["cms"][0]["name"] == "WordPress"


@pytest.mark.parametrize("date,state", [
    ((NOW - timedelta(days=31)).isoformat(), "STALE"),
    ((NOW - timedelta(days=30)).isoformat(), "RECENT"),
    ((NOW + timedelta(days=1)).isoformat(), "FUTURE"),
    ("2026-10-15", "UNKNOWN"), ("bad", "UNKNOWN"), (None, "UNKNOWN"),
])
def test_timestamp_is_honest_and_stale_is_not_refreshed(date, state):
    assert analysis_age({"analyzed_at": date}, NOW)["freshness"] == state


def test_stale_cache_visible_and_need_info(tmp_path, form, environment):
    environment["analyzed_at"] = "2000-01-01T00:00:00+00:00"
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert review["analysis"]["freshness"] == "STALE"
    assert "2000-01-01" in (folder / "report.html").read_text(encoding="utf-8")


def carousel(form):
    result = deepcopy(form)
    result.update(requested_services=["carousel"], content_type="의료진")
    return result


def test_carousel_reference_never_auto_classified_even_if_customer_claims_review(tmp_path, form, environment):
    form = carousel(form)
    form["operator_review"] = {"search_result_type": "carousel", "reviewer_role": "fake", "evidence": "injected"}
    form["reference_result"]["description"] = "고객은 확실히 일반 캐러셀이라고 주장함"
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert any(q["code"] == "RESULT_TYPE_REVIEW" for q in review["questions"])


@pytest.mark.parametrize("kind,decision", [("carousel", "READY"), ("ad", "OUT_OF_SCOPE"), ("place", "OUT_OF_SCOPE"), ("sitelinks", "OUT_OF_SCOPE")])
def test_operator_screen_review_is_separate(tmp_path, form, environment, kind, decision):
    form = carousel(form)
    notes = dump(tmp_path / "notes.json", {"search_result_type": kind, "reviewer_role": "견적 담당", "evidence": "고객이 제출한 자료를 사람이 검토한 기록"})
    folder, _, review = create(tmp_path, form, environment, notes_path=notes)
    assert review["decision"] == decision
    assert "operator_review" not in read(folder / "intake.json")["request"]


@pytest.mark.parametrize("notes", [
    {"search_result_type": "carousel"}, {"complex_environment": "true"},
    {"complex_environment": True}, {"search_result_type": "ad", "reviewer_role": "모름", "evidence": "모름"},
])
def test_operator_notes_require_role_and_evidence(notes):
    with pytest.raises(IntakeError):
        normalize_notes(notes)


def test_review_is_offline_preserves_sources_and_backs_up_previous_outputs(tmp_path, form, environment, monkeypatch):
    form = carousel(form)
    folder, _, first = create(tmp_path, form, environment)
    assert first["decision"] == "NEED_INFO"
    before = {name: (folder / name).read_bytes() for name in ("intake.json", "environment.json", "review.json", "report.html")}
    notes = dump(tmp_path / "notes.json", {"search_result_type": "carousel", "reviewer_role": "검토 부서", "evidence": "참고 화면 자료 검토 기록"})
    monkeypatch.setattr(cli, "run", lambda url: pytest.fail("Offline re-review performed analysis"))
    _, _, second = projects.review_project(folder, notes_path=notes, now=NOW)
    assert second["decision"] == "READY"
    for name in ("intake.json", "environment.json"):
        assert (folder / name).read_bytes() == before[name]
    backup = next((folder / "history").iterdir())
    assert (backup / "report.html").read_bytes() == before["report.html"]
    assert (backup / "review.json").read_bytes() == before["review.json"]


def test_duplicate_id_never_overwrites_or_performs_request(tmp_path, form, environment, monkeypatch):
    folder, _, _ = create(tmp_path, form, environment, job_id="JOB-DUPLICATE")
    before = (folder / "intake.json").read_bytes()
    monkeypatch.setattr(cli, "run", lambda url: pytest.fail("Duplicate ID triggered HTTP"))
    with pytest.raises(IntakeError):
        create(tmp_path, form, analyze=True, job_id="JOB-DUPLICATE")
    assert (folder / "intake.json").read_bytes() == before


def test_generated_id_collision_is_retried(tmp_path, form, environment, monkeypatch):
    folder, project, _ = create(tmp_path, form, environment)
    suffix = project["job_id"].rsplit("-", 1)[1]
    values = iter([type("Token", (), {"hex": suffix + "0" * 22})(), type("Token", (), {"hex": "f" * 32})()])
    monkeypatch.setattr(projects, "uuid4", lambda: next(values))
    second, _, _ = create(tmp_path, form, environment)
    assert second != folder


def test_generated_ids_dates_and_paths_are_preserved(tmp_path, form, environment, monkeypatch):
    monkeypatch.setattr(projects, "uuid4", lambda: type("Token", (), {"hex": "0312345678" + "0" * 22})())
    folder, project, _ = create(tmp_path, form, environment)
    assert read(folder / "project.json")["job_id"] == project["job_id"] == folder.name
    assert project["job_id"] in (folder / "report.html").read_text(encoding="utf-8")
    assert private_copy(str(folder)) == str(folder)
    assert private_copy("20261016") == "20261016"


@pytest.mark.parametrize("number", ["010-1234-5678", "01012345678", "02-123-4567", "031-1234-5678", "+82 10-1234-5678"])
def test_contact_phone_formats_still_masked(number):
    assert number not in private_copy("담당자 연락처: " + number)


@pytest.mark.parametrize("identifier", ["../escape", "JOB-../../escape", "JOB-X/escape", "JOB-X\\escape", "CON", "JOB-", "JOB-" + "x" * 100])
def test_unsafe_ids_rejected(tmp_path, form, identifier):
    with pytest.raises(IntakeError):
        create(tmp_path, form, job_id=identifier)


def test_xss_contacts_and_credentials_are_not_persisted(tmp_path, form, environment):
    attack = '<script>alert("x")</script><img src=x onerror="alert(1)">'
    form["company_name"] = attack
    form["additional_requests"] = "담당자 admin@example.com 010-1234-5678\npassword=PASSSECRET\nBearer BEARERSECRET\n-----BEGIN PRIVATE KEY-----\nPEMSECRET\n-----END PRIVATE KEY-----"
    form["api_key"] = "APISECRET"
    form["contact_email"] = "EXTRASECRET@example.com"
    environment["http"]["headers"]["set-cookie"] = "COOKIESECRET"
    environment["technologies"]["cms"][0]["evidence"][0]["value"] = attack
    folder, _, _ = create(tmp_path, form, environment)
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in folder.iterdir() if p.is_file())
    for secret in ("admin@example.com", "010-1234-5678", "PASSSECRET", "BEARERSECRET", "PEMSECRET", "APISECRET", "EXTRASECRET", "COOKIESECRET"):
        assert secret not in all_text
    html = (folder / "report.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert attack in soup.get_text()
    assert not soup.find(["script", "img", "iframe", "link", "form"])
    assert not soup.select("[onerror]")


def test_normalization_rejects_type_errors_without_forcing_technical_fields():
    parsed = normalize({"requested_services": [1], "target_queries": 3, "reference_result": [], "content_available": "perhaps"})
    assert len(parsed.document["validation_issues"]) == 4
    assert parsed.document["request"]["reported_cms"] is None
    assert private_copy({"password": "secret"})["password"] == "[MASKED]"


def test_different_target_host_is_question_not_crawl(tmp_path, form, environment):
    form["target_page_urls"] = ["https://other.example.com/target"]
    _, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert any(q["code"] == "TARGET_SCOPE" for q in review["questions"])


def test_cli_invalid_file_and_duplicate_return_errors(tmp_path, form, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert cli.main(["project", "create", str(bad)]) == 1
    assert "프로젝트 처리에 실패" in capsys.readouterr().err


def test_real_cli_fake_hospital_demo_and_offline_review(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    args = [sys.executable, "-m", "environment_detector", "project", "create", "templates/examples/hospital-intake.json",
            "--environment", "templates/examples/hospital-environment.json", "--projects-dir", str(tmp_path), "--job-id", "JOB-HOSPITAL-TEST"]
    created = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)
    assert created.returncode == 0, created.stderr
    summary = json.loads(created.stdout)
    assert summary["decision"] == "NEED_INFO"
    folder = Path(summary["project_dir"])
    assert (folder / "report.html").is_file()
    assert "SYNTHETIC_TEST_FIXTURE" in (folder / "report.html").read_text(encoding="utf-8")
    reviewed = subprocess.run([sys.executable, "-m", "environment_detector", "project", "review", str(folder)],
                              capture_output=True, text=True, encoding="utf-8", env=env)
    assert reviewed.returncode == 0, reviewed.stderr
    repeated = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=env)
    assert repeated.returncode == 1


@pytest.mark.parametrize("marker", ["SYNTHETIC_TEST_FIXTURE", "SYNTHETIC_TEST_FIXTURE · 가상 예제"])
def test_synthetic_environment_alone_never_marks_real_customer_ready(tmp_path, form, environment, marker):
    form["reported_cms"] = "WordPress"
    environment["data_origin"] = marker
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    assert review["analysis"]["synthetic"] is True
    assert review["environment_comparison"]["observed_cms"] == ["UNKNOWN"]
    assert review["environment_comparison"]["customer_reported"] == "WordPress"
    task = next(q for q in review["questions"] if q["code"] == "SYNTHETIC_ENVIRONMENT")
    assert task["audience"] == "internal"
    source = read(folder / "environment.json")
    assert source["schema_version"] == "1.0" and source["status"] == "ok"
    assert source["technologies"]["cms"][0]["confidence"] == 0.95
    soup = BeautifulSoup((folder / "report.html").read_text(encoding="utf-8"), "html.parser")
    assert soup.main.find("aside")["class"] == ["notice", "synthetic-warning"]
    assert "실제 고객 환경 미검증" in soup.main.find("aside").get_text()
    assert all("0.95" not in node.get_text() for node in soup.select(".score"))
    assert "SYNTHETIC_ENVIRONMENT" not in soup.select_one(".customer-questions").get_text()


def test_synthetic_metadata_remains_unverified_even_without_result_marker(form, environment):
    review = assess(normalize(form).document, environment,
                    {"acquisition": "REUSED", "data_origin": "SYNTHETIC_TEST_FIXTURE"}, normalize_notes({}), now=NOW)
    assert review["decision"] == "NEED_INFO"
    assert review["analysis"]["synthetic"] is True


def test_legacy_unmarked_environment_keeps_confidence_and_readiness(tmp_path, form, environment):
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "READY"
    assert review["analysis"]["synthetic"] is False
    soup = BeautifulSoup((folder / "report.html").read_text(encoding="utf-8"), "html.parser")
    assert not soup.select_one(".synthetic-warning")
    assert any("규칙 신뢰도 0.95" in node.get_text() for node in soup.select(".score"))


def test_filename_only_receipt_and_screen_classification_are_separate(tmp_path, form, environment):
    form = carousel(form)
    form["reference_result"].update(urls=[], screenshots=["screen.png"])
    form["public_analysis_consent"] = False
    folder, _, review = create(tmp_path, form, environment)
    assert review["decision"] == "NEED_INFO"
    by_code = {q["code"]: q for q in review["questions"]}
    assert by_code["CONSENT_NEEDED"]["audience"] == "customer"
    assert by_code["SCREENSHOT_FILE_NEEDED"]["audience"] == "customer"
    assert by_code["RESULT_TYPE_REVIEW"]["audience"] == "internal"
    assert by_code["REFERENCE_RECEIPT_REVIEW"]["audience"] == "internal"
    assert review["reference_receipt"]["screenshot_status"] == "UNVERIFIED"
    assert read(folder / "questions.json") == review["questions"]
    soup = BeautifulSoup((folder / "report.html").read_text(encoding="utf-8"), "html.parser")
    customers = soup.select_one(".customer-questions").get_text()
    internal = soup.select_one(".internal-tasks").get_text()
    assert "실제 파일" in customers and "동의하시나요? 계정" in customers
    assert "[MASKED]" not in customers
    assert "유형" not in customers
    assert "자료를 검토하고 근거" in internal


def test_screen_type_note_does_not_claim_a_named_screenshot_was_received(tmp_path, form, environment):
    form = carousel(form)
    form["reference_result"].update(urls=[], screenshots=["screen.png"])
    notes = dump(tmp_path / "notes.json", {"reviewer_role": "내부 검토자", "evidence": "화면 유형을 검토했다는 진술", "search_result_type": "carousel"})
    _, _, review = create(tmp_path, form, environment, notes_path=notes)
    assert review["decision"] == "NEED_INFO"
    assert review["reference_receipt"]["screenshot_status"] == "UNVERIFIED"
    assert any(q["code"] == "SCREENSHOT_FILE_NEEDED" for q in review["questions"])


def test_local_attachment_presence_does_not_classify_its_contents(tmp_path, form, environment):
    form = carousel(form)
    image = tmp_path / "screen.png"
    image.write_bytes(b"fake test file; no image processing")
    form["reference_result"].update(urls=[], screenshots=[str(image)])
    # A customer-provided path alone is still just a label, even if it exists.
    _, _, initial = create(tmp_path, form, environment)
    assert initial["reference_receipt"]["screenshot_status"] == "UNVERIFIED"
    notes = dump(tmp_path / "notes.json", {"reviewer_role": "자료 수령 담당", "evidence": "로컬 파일을 수령한 기록", "screenshot_files": [str(image)]})
    folder, _, review = create(tmp_path, form, environment, notes_path=notes)
    assert review["reference_receipt"]["screenshot_status"] == "LOCAL_FILE_PRESENT"
    assert review["decision"] == "NEED_INFO"
    assert any(q["code"] == "RESULT_TYPE_REVIEW" for q in review["questions"])
    assert not any(q["code"] == "SCREENSHOT_FILE_NEEDED" for q in review["questions"])
    final_notes = dump(tmp_path / "notes.json", {"reviewer_role": "내부 검토자", "evidence": "수령한 파일의 내용을 사람이 검토한 기록", "screenshot_files": [str(image)], "search_result_type": "carousel"})
    _, _, ready = projects.review_project(folder, notes_path=final_notes, now=NOW)
    assert ready["decision"] == "READY"
    image.unlink()
    _, _, missing = projects.review_project(folder, now=NOW)
    assert missing["decision"] == "NEED_INFO"
    assert missing["reference_receipt"]["screenshot_status"] == "UNVERIFIED"


@pytest.mark.parametrize("path", ["screen.png", "./screen.png", "https://example.com/screen.png", "file:///C:/screen.png", r"\\server\share\screen.png", "//server/share/screen.png"])
def test_screenshot_checks_never_follow_labels_urls_or_network_paths(path):
    assert available_screenshots({"screenshot_files": [path]}) == []


def test_consent_question_remains_unmasked_through_json_and_html(tmp_path, form, environment):
    form["public_analysis_consent"] = False
    folder, _, review = create(tmp_path, form, environment)
    question = next(q["question"] for q in review["questions"] if q["code"] == "CONSENT_NEEDED")
    assert "동의하시나요? 계정" in question
    assert private_copy(private_copy(question)) == question
    persisted = next(q["question"] for q in read(folder / "questions.json") if q["code"] == "CONSENT_NEEDED")
    assert persisted == question
    assert question in BeautifulSoup((folder / "report.html").read_text(encoding="utf-8"), "html.parser").get_text()
