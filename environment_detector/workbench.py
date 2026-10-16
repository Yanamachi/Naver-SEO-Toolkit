"""Offline projection of existing project artifacts. Never runs an analyzer."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

from .intake import IntakeError, SERVICES, private_copy, safe_url
from .pre_review import analysis_age, cms_key
from .projects import write_text
from .report import is_synthetic, result_state, validate_result
from .safety import DetectorError

RESULTS = {"PASS", "ISSUE", "WARNING", "NOT_VERIFIED", "NOT_APPLICABLE"}
JOB_ID = re.compile(r"JOB-[A-Za-z0-9][A-Za-z0-9_-]{0,59}\Z")
INTERNAL_CODES = {"RESULT_TYPE_REVIEW", "REFERENCE_RECEIPT_REVIEW", "SYNTHETIC_ENVIRONMENT", "ENVIRONMENT_DATE", "ENVIRONMENT_UNKNOWN", "ENVIRONMENT_UNAVAILABLE"}
STAGES = (
    ("intake", "01", "고객 의뢰 접수", True, "업체명·공개 URL·요청 서비스와 입력 검증 항목 확인"),
    ("environment", "02", "홈페이지 환경 분석", True, "동일 URL의 실제 응답·기술 근거·분석 시점을 확인"),
    ("review", "03", "사전 수주 검토", True, "현재 자료와 일치하는 판정 및 고객 질문·내부 검토 확인"),
    ("seo", "04", "SEO 읽기 전용 진단", True, "승인한 대상의 실제 진단 결과·실패·미검증·우선순위 검토"),
    ("carousel", "05", "Carousel Builder", False, "향후 개발: 실제 콘텐츠·화면 유형·권한·승인 확보 후 별도 구현"),
    ("images", "06", "Image Optimizer", False, "향후 개발: 원본 이미지·사용 권한·품질 기준 확보 후 별도 구현"),
    ("adapters", "07", "환경별 적용 어댑터", False, "향후 개발: 실제 수정 경로·작업 승인·백업·롤백 확인"),
    ("delivery", "08", "최종 검증 및 납품", False, "향후 개발: 승인한 변경에 대한 검증 기록·고객 최종 검수"),
)


def safe_path(path):
    path = Path(path).absolute()
    if str(path).startswith(("\\\\", "//")):
        raise IntakeError("네트워크 공유 경로는 통합 화면 입력으로 허용하지 않습니다.")
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise IntakeError("심볼릭 링크·정션 경로는 허용하지 않습니다.")
    return path


def load_json(folder, name, validator):
    path = folder / name
    record = {"filename": name, "state": "MISSING", "data": None, "note": "파일 미생성"}
    try:
        safe_path(path)
        if not path.exists():
            return record
        if not path.is_file():
            raise ValueError("not file")
        with path.open("rb") as handle:
            raw = handle.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError("too large")
        data = json.loads(raw.decode("utf-8-sig"))
        validator(data)
        record.update(state="AVAILABLE", data=data, note="저장된 JSON 읽음")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        record.update(state="INVALID", note="형식·스키마·5 MiB 제한·파일 경로를 확인하세요. 결과로 사용하지 않았습니다.")
    return record


def require(condition):
    if not condition:
        raise ValueError("Invalid saved artifact")


def valid_questions(data):
    require(isinstance(data, list))
    for q in data:
        require(isinstance(q, dict) and isinstance(q.get("question"), str))
        require(q.get("audience") in {None, "customer", "internal"})
        require(all(q.get(k) is None or isinstance(q[k], str) for k in ("code", "field")))


def valid_intake(data):
    require(isinstance(data, dict) and data.get("schema_version") == "intake-1.0")
    request = data["request"]
    require(isinstance(request, dict))
    for key in ("company_name", "site_url", "reported_cms", "industry", "modification_owner", "modification_route"):
        require(request.get(key) is None or isinstance(request[key], str))
    for key in ("requested_services", "target_page_urls", "target_queries"):
        require(isinstance(request.get(key, []), list) and all(isinstance(v, str) for v in request.get(key, [])))
    require(isinstance(data.get("validation_issues", []), list))


def valid_project(data):
    require(isinstance(data, dict) and data.get("schema_version") == "project-1.0" and isinstance(data.get("job_id"), str))
    require(isinstance(data.get("environment", {}), dict))


def valid_review(data):
    require(isinstance(data, dict) and data.get("schema_version") == "pre-review-1.0")
    require(data.get("decision") in {"READY", "NEED_INFO", "CUSTOM_QUOTE", "OUT_OF_SCOPE"})
    require(isinstance(data.get("reasons"), list) and all(isinstance(v, str) for v in data["reasons"]))
    valid_questions(data.get("questions", []))
    require(isinstance(data.get("analysis", {}), dict) and isinstance(data.get("environment_comparison", {}), dict))


def valid_environment(data):
    validate_result(data)
    if data.get("http") is not None:
        require(isinstance(data["http"], dict) and type(data["http"].get("status_code")) is int)


def valid_seo(data):
    require(isinstance(data, dict) and data.get("schema_version") == "seo-audit-1.0")
    require(data.get("status") in {"COMPLETE", "PARTIAL", "BLOCKED"} and isinstance(data.get("job_id"), str))
    for name in ("summary", "scope", "customer", "environment_reference", "options"):
        require(isinstance(data.get(name), dict))
    require(type(data["options"].get("max_pages")) is int and data["options"]["max_pages"] >= 1)
    require(data["options"].get("indexing_goal") in {"unknown", "index", "noindex"})
    require(all(type(data["scope"].get(k)) is bool for k in ("crawl_approved", "sitemaps_approved")))
    require(isinstance(data.get("limitations"), list) and all(isinstance(v, str) for v in data["limitations"]))
    require(isinstance(data["summary"].get("results"), dict))
    for key in ("page_count", "analyzed_pages", "failed_pages", "request_count"):
        require(type(data["summary"].get(key)) is int and data["summary"][key] >= 0)
    require(isinstance(data.get("findings"), list) and isinstance(data.get("pages"), list))
    require(isinstance(data.get("customer_questions", []), list) and all(isinstance(q, str) for q in data.get("customer_questions", [])))
    for f in data["findings"]:
        require(isinstance(f, dict) and f.get("result") in RESULTS and f.get("severity") in {"HIGH", "MEDIUM", "LOW", "INFO"})
        require(all(isinstance(f.get(k), str) for k in ("id", "url", "title", "reason", "recommendation")))
        require("evidence" in f and isinstance(f.get("documentation"), list))
    require(data["summary"]["analyzed_pages"] <= data["summary"]["page_count"])
    require(isinstance(data["scope"].get("explicit_urls"), list) and all(isinstance(v, str) for v in data["scope"]["explicit_urls"]))
    require(all(isinstance(p, dict) and isinstance(p.get("state"), str) for p in data["pages"]))
    require(data["summary"]["page_count"] == len(data["pages"]))
    require(data["summary"]["analyzed_pages"] == sum(p["state"] == "ANALYZED" for p in data["pages"]))


def build_workbench(folder, *, now=None):
    folder = safe_path(folder)
    if not folder.is_dir():
        raise IntakeError("존재하는 고객 프로젝트 폴더를 지정하세요.")
    now = now or datetime.now(timezone.utc)
    specs = {"project": ("project.json", valid_project), "intake": ("intake.json", valid_intake),
             "environment": ("environment.json", valid_environment), "review": ("review.json", valid_review),
             "questions": ("questions.json", valid_questions), "seo": ("seo-audit.json", valid_seo)}
    artifacts = {key: load_json(folder, *spec) for key, spec in specs.items()}
    intake = artifacts["intake"]["data"]
    if intake is None:
        raise IntakeError("유효한 intake-1.0 의뢰서가 필요합니다. intake.json을 확인하세요.")
    project = artifacts["project"]["data"] or {}
    request = intake["request"]
    notices = []
    site = None
    try:
        site = safe_url(request.get("site_url") or "")
    except (DetectorError, ValueError):
        notices.append("공개 홈페이지 URL 미확인: 실제 분석 명령을 제공하지 않습니다.")
    identifier = project.get("job_id") or folder.name
    for key in ("environment", "seo"):
        record = artifacts[key]
        data = record["data"]
        if data is None:
            continue
        try:
            source_url = data.get("request_url") if key == "environment" else data["customer"].get("site_url")
            require(site is not None and safe_url(source_url or "") == site)
            if key == "seo":
                require(data["job_id"] == identifier)
        except (DetectorError, ValueError, TypeError):
            record.update(state="INVALID", data=None, note="의뢰 URL 또는 작업 ID 불일치: 이 고객의 결과로 사용하지 않았습니다.")
    for key, record in artifacts.items():
        if record["state"] == "INVALID":
            notices.append(record["filename"] + ": " + record["note"])
    env = artifacts["environment"]["data"]
    review = artifacts["review"]["data"]
    seo = artifacts["seo"]["data"]
    synthetic_project = is_synthetic(project) or is_synthetic(intake)
    env_synthetic = bool((env and is_synthetic(env)) or is_synthetic(project.get("environment", {})) or (review or {}).get("analysis", {}).get("synthetic") is True)
    seo_synthetic = bool(seo and is_synthetic(seo))
    questions = []
    # Both saved sources are read, without silently replacing either one.
    for q in [*(review or {}).get("questions", []), *(artifacts["questions"]["data"] or [])]:
        q = {**q, "audience": q.get("audience") or ("internal" if q.get("code") in INTERNAL_CODES else "customer")}
        if q not in questions:
            questions.append(q)
    if review and artifacts["questions"]["data"] is not None and review.get("questions", []) != artifacts["questions"]["data"]:
        notices.append("review.json과 questions.json이 다릅니다. 양쪽 질문을 보존해 표시하며 재검토가 필요합니다.")
    for q in (seo or {}).get("customer_questions", []):
        if not any(item["question"] == q and item["audience"] == "customer" for item in questions):
            questions.append({"audience": "customer", "question": q, "code": "SEO_FOLLOWUP", "field": "seo"})
    if not site:
        questions.append({"audience": "customer", "question": "올바른 공개 홈페이지 URL을 알려주세요.", "code": "WORKBENCH_SITE_URL"})
    for key, label in (("company_name", "업체명"), ("requested_services", "요청 서비스")):
        if not request.get(key):
            questions.append({"audience": "customer", "question": label + "를 알려주세요.", "code": "WORKBENCH_" + key.upper()})
    if request.get("public_analysis_consent") is not True and not any(q.get("code") == "CONSENT_NEEDED" for q in questions):
        questions.append({"audience": "customer", "question": "공개 영역의 읽기 전용 분석 동의를 확인해 주세요. 계정·비밀번호는 전달하지 마세요.", "code": "WORKBENCH_CONSENT"})
    states = {}
    intake_ready = bool(request.get("company_name") and site and request.get("requested_services") and not intake.get("validation_issues"))
    states["intake"] = ("NOT_VERIFIED", "가상 의뢰의 접수 예시입니다.") if synthetic_project else ("COMPLETED", "정규화 의뢰서의 기본 항목을 확보했습니다. 실제 권한 확인과는 별도입니다.") if intake_ready else ("NEED_INFO", "업체명·URL·요청 서비스 또는 입력 검증 항목을 확인하세요.")
    env_age = analysis_age(env or {}, now)
    if not env:
        states["environment"] = ("NOT_STARTED" if artifacts["environment"]["state"] == "MISSING" else "NEED_REVIEW", "환경 JSON이 없거나 사용할 수 없습니다.")
    elif env_synthetic or synthetic_project:
        states["environment"] = ("NOT_VERIFIED", "가상 기술 단서이며 실제 고객 환경 검증은 완료되지 않았습니다.")
    elif env.get("status") != "ok" or env.get("errors"):
        states["environment"] = ("BLOCKED", "분석 오류·보안 차단을 해결하기 위한 담당자 확인이 필요합니다.")
    elif not isinstance(env.get("http"), dict) or not 200 <= env["http"].get("status_code", 0) < 300 or result_state(env) == "unknown" or not any(i["name"] not in {"UNKNOWN", ""} and i["evidence"] for c in ("cms", "frontend", "backend") for i in env["technologies"][c]):
        states["environment"] = ("NOT_VERIFIED", "정상 HTTP 응답 또는 식별 가능한 기술 근거가 부족합니다. UNKNOWN을 자체 개발로 해석하지 않습니다.")
    elif env_age["freshness"] != "RECENT":
        states["environment"] = ("NEED_REVIEW", "과거·미래·불명 시점의 결과입니다. 변경 여부를 확인하세요.")
    else:
        states["environment"] = ("COMPLETED", "공개 응답의 기술 단서를 확보했습니다. 원본 서버·수정 권한은 미검증입니다.")
    review_stale = bool(review and env and review.get("analysis", {}).get("analyzed_at") != env.get("analyzed_at"))
    if review and review.get("environment_comparison", {}).get("customer_reported", "UNKNOWN") != (request.get("reported_cms") or "UNKNOWN"):
        review_stale = True
    if review_stale:
        notices.append("사전 검토가 참조한 환경 분석 시점 또는 고객 CMS 진술이 현재 자료와 다릅니다. 오프라인 재검토가 필요합니다.")
    if not review:
        states["review"] = ("NOT_STARTED" if artifacts["review"]["state"] == "MISSING" else "NEED_REVIEW", "사전 수주 검토 결과를 생성하거나 형식을 확인하세요.")
    elif artifacts["project"]["state"] != "AVAILABLE":
        states["review"] = ("NEED_REVIEW", "프로젝트 메타데이터가 없어 연결 상태와 저장된 판정을 확인해야 합니다.")
    elif review_stale or any("questions.json" in n for n in notices):
        states["review"] = ("NEED_REVIEW", "저장된 자료 사이에 불일치가 있습니다.")
    elif not intake_ready:
        states["review"] = ("NEED_INFO", "현재 의뢰 정보가 부족합니다. 과거의 저장 판정만으로 진행하지 않습니다.")
    elif review["decision"] == "OUT_OF_SCOPE":
        states["review"] = ("BLOCKED", "저장된 판정은 제공 서비스 범위 밖입니다. 담당자와 범위를 협의하세요.")
    elif review["decision"] == "NEED_INFO" or questions:
        states["review"] = ("NEED_INFO", "고객 질문 또는 내부 검토가 남아 있습니다. 저장된 수주 판정은 별도로 유지합니다.")
    elif synthetic_project or env_synthetic:
        states["review"] = ("NOT_VERIFIED", "가상 자료의 판정이며 실제 견적·권한 확인이 아닙니다.")
    else:
        states["review"] = ("READY" if review["decision"] == "READY" else "NEED_REVIEW", "견적 검토가 가능하거나 별도 기술 견적 검토가 필요합니다. 운영 작업 승인이 아닙니다.")
    findings = (seo or {}).get("findings", [])
    seo_scope_changed = False
    if seo:
        try:
            current_targets = {safe_url(v) for v in request.get("target_page_urls", []) or [site or ""]}
            saved_targets = {safe_url(v) for v in seo["scope"].get("explicit_urls", [])}
            seo_scope_changed = current_targets != saved_targets
        except (DetectorError, ValueError, TypeError):
            seo_scope_changed = True
        if seo_scope_changed:
            notices.append("현재 의뢰 대상과 저장된 SEO 분석 범위가 다릅니다. 과거 결과로 표시하며 새 범위 검토가 필요합니다.")
    priorities = sorted((f for f in findings if f["result"] in {"ISSUE", "WARNING"}), key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}[f["severity"]], f["result"] != "ISSUE"))
    seo_age = analysis_age(seo or {}, now)
    if not seo:
        states["seo"] = ("NOT_STARTED" if artifacts["seo"]["state"] == "MISSING" else "NEED_REVIEW", "SEO 진단 JSON이 없습니다. 빈 결과를 정상 분석으로 만들지 않습니다.")
    elif seo_synthetic or synthetic_project:
        states["seo"] = ("NOT_VERIFIED", "모의 HTTP 또는 가상 프로젝트의 진단이며 실제 고객 SEO는 미검증입니다.")
    elif seo["status"] == "BLOCKED":
        states["seo"] = ("BLOCKED", "HTML 분석이 완료되지 않았습니다. 접근·동의·차단 사유를 확인하세요.")
    elif seo_scope_changed or seo_age["freshness"] != "RECENT" or priorities or seo["status"] == "PARTIAL" or any(f["result"] == "NOT_VERIFIED" for f in findings):
        states["seo"] = ("NEED_REVIEW", "저장된 진단의 문제·미검증·시점을 담당자가 검토해야 합니다. 수정 완료를 뜻하지 않습니다.")
    elif seo["summary"]["analyzed_pages"] < 1 or not findings:
        states["seo"] = ("NOT_VERIFIED", "실제 분석 페이지 또는 진단 근거가 없습니다.")
    else:
        states["seo"] = ("COMPLETED", "설정한 초기 HTML 검사 범위를 완료했습니다. 실제 색인·순위나 개선 작업 완료는 아닙니다.")
    comparison = {"customer_reported": request.get("reported_cms") or "UNKNOWN", "observed_cms": [], "state": "UNVERIFIED"}
    if env and not env_synthetic and not synthetic_project:
        comparison["observed_cms"] = [i["name"] for i in env["technologies"]["cms"] if i["name"] != "UNKNOWN" and i["evidence"]]
        known = cms_key(request.get("reported_cms"))
        if known and comparison["observed_cms"]:
            comparison["state"] = "CONSISTENT_CLUES" if known in comparison["observed_cms"] else "DIFFERENT_CLUES"
    for stage, *_ in STAGES[4:]:
        requested = stage not in {"carousel", "images"} or stage in request.get("requested_services", [])
        states[stage] = ("NOT_STARTED", "프로그램 미구현 · 고객 작업 실행 및 완료 산출물 없음" if requested else "프로그램 미구현 · 현재 고객 의뢰에 포함되지 않은 서비스")
    reports = []
    for name, label in (("report.html", "사전 검토 보고서"), ("seo-report.html", "SEO 상세 보고서"), ("environment-report.html", "환경 상세 보고서")):
        path = folder / name
        try:
            safe_path(path)
            exists = path.is_file() and path.stat().st_size > 0
        except (OSError, IntakeError):
            exists = False
        reports.append({"filename": name, "label": label, "available": exists})
    model = {"job_id": identifier, "id_from_metadata": bool(project.get("job_id")), "generated_at": now.isoformat(),
             "artifacts": artifacts, "states": states, "questions": questions, "priorities": priorities,
             "comparison": comparison, "notices": notices, "reports": reports, "env_age": env_age, "seo_age": seo_age,
             "synthetic": synthetic_project or env_synthetic or seo_synthetic,
             "synthetic_project": synthetic_project, "env_synthetic": env_synthetic, "seo_synthetic": seo_synthetic,
             "seo_counts": dict(Counter(f["result"] for f in findings))}
    # Mask all source data before rendering or composing the bounded Codex brief.
    model = private_copy(model)
    from .workbench_actions import actions_for
    model["actions"] = actions_for(model, folder, site)
    return model


def save_dashboard(folder, *, now=None):
    now = now or datetime.now(timezone.utc)
    folder = safe_path(folder)
    output = safe_path(folder / "dashboard.html")
    if output.exists() and not output.is_file():
        raise IntakeError("dashboard.html 경로는 일반 파일이어야 합니다.")
    model = build_workbench(folder, now=now)
    from .workbench_report import render_dashboard
    html = render_dashboard(model)
    if output.exists():
        history = safe_path(folder / "history")
        history.mkdir(exist_ok=True)
        backup = history / ("dashboard-" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8] + ".html")
        backup.write_bytes(output.read_bytes())
    write_text(output, html)
    return output, model
