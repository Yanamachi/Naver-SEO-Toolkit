"""Local customer projects, explicit consent gate, and offline cache reuse."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4

from .detect import CATEGORIES, unknown
from .intake import IntakeError, normalize, normalize_notes, private_copy, read_object, safe_url
from .pre_review import analysis_age, assess
from .project_report import render_project
from .report import validate_result
from .safety import DetectorError


def write_text(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".project-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json(path, data):
    write_text(path, json.dumps(private_copy(data), ensure_ascii=False, indent=2) + "\n")


def unexamined(url, code, message, now):
    return {"schema_version": "1.0", "status": "error", "analyzed_at": now.isoformat(),
            "request_url": url or "UNKNOWN", "final_url": None, "http": None,
            "technologies": {key: [unknown()] for key in CATEGORIES}, "development_model": unknown(),
            "errors": [{"code": code, "message": message}]}


def matching_snapshot(path, url):
    data = read_object(path)
    try:
        validate_result(data)
        if safe_url(data["request_url"]) != url:
            raise IntakeError("지정한 환경 JSON과 의뢰 URL이 일치하지 않습니다.")
        if data["status"] == "ok":
            if not isinstance(data.get("http"), dict) or not isinstance(data["http"].get("status_code"), int) or not 200 <= data["http"]["status_code"] < 300:
                raise ValueError("Invalid success response")
    except (ValueError, TypeError, KeyError, DetectorError) as exc:
        raise IntakeError("환경 JSON의 형식 또는 의뢰 URL 일치 여부를 확인하세요.") from exc
    return data


def choose_cache(folder, url, now):
    if not folder.is_dir():
        return None, None
    candidates = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = matching_snapshot(path, url)
        except IntakeError:
            continue
        age = analysis_age(data, now)
        # Prefer the newest successful result. Unknown/future timestamps rank last.
        rank_age = age["age_days"] if age["freshness"] in {"RECENT", "STALE"} else float("inf")
        candidates.append((data["status"] == "ok", -rank_age, path, data))
    if not candidates:
        return None, None
    _, _, path, data = max(candidates, key=lambda item: (item[0], item[1], item[2].name))
    return data, path


def reserve_project(root, job_id, now):
    if job_id is not None and not re.fullmatch(r"JOB-[A-Za-z0-9][A-Za-z0-9_-]{0,59}", job_id):
        raise IntakeError("작업 ID는 JOB-로 시작하는 영문·숫자·밑줄·하이픈만 허용합니다.")
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        identifier = job_id or f"JOB-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:10]}"
        folder = root / identifier
        try:
            folder.mkdir(mode=0o700)
        except FileExistsError:
            if job_id is not None:
                raise IntakeError("동일 작업 ID가 이미 있습니다. 새 ID를 사용하세요.")
            continue
        # Protect even a custom output folder inside another Git worktree.
        (folder / ".gitignore").write_text("*\n", encoding="utf-8")
        return folder, identifier
    raise IntakeError("새 작업 ID를 예약하지 못했습니다.")


def save_review(folder, project, intake, environment, review):
    write_json(folder / "review.json", review)
    write_json(folder / "questions.json", review["questions"])
    write_text(folder / "report.html", render_project(project, intake, environment, review))


def create_project(intake_path, *, projects_dir=Path("customer-data/projects"), job_id=None,
                   environment_path=None, reuse_dir=None, analyze=False, notes_path=None, now=None):
    now = now or datetime.now(timezone.utc)
    parsed = normalize(read_object(intake_path))
    intake = parsed.document
    notes = normalize_notes(read_object(notes_path)) if notes_path else normalize_notes({})
    if sum((environment_path is not None, reuse_dir is not None, analyze)) > 1:
        raise IntakeError("환경 JSON·재사용 폴더·새 분석 중 하나만 선택하세요.")
    environment = None
    source = None
    if parsed.site_url and not analyze:
        if environment_path:
            environment = matching_snapshot(environment_path, parsed.site_url)
            source = environment_path
        else:
            environment, source = choose_cache(reuse_dir or Path("results"), parsed.site_url, now)
    # Reserve before any possible live request; duplicate IDs never trigger HTTP.
    folder, identifier = reserve_project(projects_dir, job_id, now)
    acquisition = "REUSED" if environment is not None else "NOT_REQUESTED"
    if environment is None:
        code, message = "ANALYSIS_NOT_REQUESTED", "재사용할 동일 URL 결과가 없고 새 분석을 요청하지 않았습니다."
        if not parsed.site_url:
            code, message = "INVALID_SITE_URL", "공개 홈페이지 URL을 확인해야 합니다."
        elif analyze and intake["request"]["public_analysis_consent"] is not True:
            code, message = "CONSENT_REQUIRED", "명시적인 공개 영역 분석 동의가 없어 사이트를 요청하지 않았습니다."
        elif analyze:
            from .cli import run
            environment = run(parsed.site_url)
            acquisition = "LIVE"
        if environment is None:
            environment = unexamined(intake["request"]["site_url"], code, message, now)
    metadata = {"acquisition": acquisition, "source_filename": source.name if source else None,
                "data_origin": environment.get("data_origin", "OBSERVED" if environment["status"] == "ok" else "UNAVAILABLE")}
    project = {"schema_version": "project-1.0", "job_id": identifier, "created_at": now.isoformat(),
               "environment": metadata, "notes": notes, "phase": "PRE_QUOTE", "production_changes": False}
    environment = private_copy(environment)
    review = assess(intake, environment, metadata, notes, now=now)
    write_json(folder / "intake.json", intake)
    write_json(folder / "environment.json", environment)
    write_json(folder / "project.json", project)
    save_review(folder, project, intake, environment, review)
    return folder, project, review


def review_project(folder, *, notes_path=None, now=None):
    """Re-review persisted inputs, never request any URL."""
    now = now or datetime.now(timezone.utc)
    if folder.is_symlink() or any((folder / name).is_symlink() for name in ("project.json", "intake.json", "environment.json", "review.json", "questions.json", "report.html", "history")):
        raise IntakeError("프로젝트 또는 산출물 심볼릭 링크는 허용하지 않습니다.")
    project = read_object(folder / "project.json")
    intake = read_object(folder / "intake.json")
    environment = read_object(folder / "environment.json")
    try:
        validate_result(environment)
        if project["schema_version"] != "project-1.0" or intake["schema_version"] != "intake-1.0":
            raise ValueError("Invalid schema")
        notes = normalize_notes(read_object(notes_path)) if notes_path else normalize_notes(project["notes"])
        review = assess(intake, environment, project["environment"], notes, now=now)
    except (KeyError, TypeError, ValueError) as exc:
        raise IntakeError("프로젝트 JSON 형식을 확인하세요.") from exc
    backup = folder / "history" / (now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    backup.mkdir(parents=True)
    for name in ("project.json", "review.json", "questions.json", "report.html"):
        if (folder / name).is_file():
            (backup / name).write_bytes((folder / name).read_bytes())
    project["notes"] = notes
    write_json(folder / "project.json", project)
    save_review(folder, project, intake, environment, review)
    return folder, project, review
