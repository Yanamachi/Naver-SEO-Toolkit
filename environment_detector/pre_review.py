"""Conservative quote triage; never a deployment or search-display approval."""

from datetime import datetime, timezone

from .intake import SERVICES, available_screenshots
from .report import is_synthetic

POSSIBLE_WORK = ["의뢰 범위와 누락 자료 정리", "저장된 공개 기술 단서 검토", "추가 질문 작성 및 견적 범위 검토"]
PERMISSIONS = ["실제 수정 전 고객의 별도 작업 범위 승인", "수정 권한 보유자의 작업 경로 확인 및 최소 권한 제공",
               "백업·복구 담당자·테스트·운영 반영 일정의 별도 합의", "콘텐츠·이미지 사용 및 최종 검수 승인"]
LIMITS = ["READY는 견적 검토용이며 운영 반영·배포 승인이나 작업 성공을 뜻하지 않습니다.",
          "수정 권한·배포 가능 여부는 고객 진술 및 담당자 확인 전까지 미검증입니다.",
          "네이버의 캐러셀 표시·검색 순위·노출 시점은 보장하거나 자동 확정하지 않습니다.",
          "고객의 희망 화면과 담당자 검토 기록을 분리하며 스크린샷을 자동 판독하지 않습니다.",
          "이번 단계에서는 SEO·캐러셀·이미지 작업이나 운영 사이트 변경을 수행하지 않습니다."]


def analysis_age(environment, now):
    value = environment.get("analyzed_at")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError("Missing timezone")
        age = (now - date.astimezone(timezone.utc)).total_seconds() / 86400
    except (ValueError, TypeError, AttributeError, OverflowError):
        return {"analyzed_at": value, "age_days": None, "freshness": "UNKNOWN"}
    return {"analyzed_at": value, "age_days": round(age, 2),
            "freshness": "FUTURE" if age < -5 / 1440 else "STALE" if age > 30 else "RECENT"}


def cms_key(value):
    return {"wordpress": "WordPress", "워드프레스": "WordPress", "imweb": "Imweb", "아임웹": "Imweb",
            "cafe24": "Cafe24", "카페24": "Cafe24", "custom": "CUSTOM", "자체 개발": "CUSTOM",
            "자체 개발 홈페이지": "CUSTOM"}.get((value or "").strip().lower())


def assess(intake, environment, metadata, notes, *, now=None):
    now = now or datetime.now(timezone.utc)
    request = intake["request"]
    questions = []

    def ask(code, text, field, audience="customer"):
        if not any(q["code"] == code and q["field"] == field for q in questions):
            questions.append({"code": code, "field": field, "question": text, "audience": audience})

    for issue in intake["validation_issues"]:
        ask(issue["code"], issue["question"], issue["field"])
    for key, label in (("company_name", "업체명"), ("industry", "업종"), ("site_url", "홈페이지 URL"),
                       ("requested_services", "요청 작업"), ("target_queries", "원하는 검색어"),
                       ("target_page_urls", "작업 대상 페이지 URL"), ("modification_owner", "홈페이지 수정 권한 보유자"),
                       ("modification_route", "수정 담당자와 협의할 작업 경로(관리자 설정·개발사 전달 등)"),
                       ("desired_schedule", "희망 일정 또는 협의 가능 여부")):
        if not request.get(key):
            ask("MISSING_" + key.upper(), label + "을 알려주세요.", key)
    reference = request["reference_result"]
    screenshot_files = available_screenshots(notes)
    if not reference["urls"] and not screenshot_files:
        if reference["screenshots"] or notes.get("screenshot_files"):
            ask("SCREENSHOT_FILE_NEEDED", "스크린샷 자료명만으로는 실제 자료 확보를 확인할 수 없습니다. 참고 화면의 실제 파일 또는 참고 URL을 전달해 주세요.", "reference_result.screenshots")
            ask("REFERENCE_RECEIPT_REVIEW", "고객 자료를 수령한 뒤 담당자 검토 기록의 screenshot_files에 로컬 실파일 절대 경로를 기록하고 재검토하세요. 자료명·파일 존재만으로 화면 내용이나 유형을 확정하지 마세요.", "reference_result.screenshots", "internal")
        else:
            ask("REFERENCE_NEEDED", "원하는 검색 화면의 참고 URL이나 실제 스크린샷 파일을 전달해 주세요. 화면 유형은 별도 검토합니다.", "reference_result")
    if not reference["device"]:
        ask("DEVICE_NEEDED", "참고 검색 화면은 PC·모바일·둘 다 중 어느 화면인가요?", "reference_result.device")
    supported = [s for s in request["requested_services"] if s in SERVICES]
    unsupported = [s for s in request["requested_services"] if s not in SERVICES]
    if unsupported and supported:
        ask("MIXED_SCOPE", "제공 범위 밖의 요청이 섞여 있습니다. 캐러셀·SEO·이미지 최적화의 견적 범위로 조정할 수 있나요?", "requested_services")
    if request["public_analysis_consent"] is not True:
        ask("CONSENT_NEEDED", "새 공개 영역 분석이 필요할 경우 해당 홈페이지의 비침투적 분석에 동의하시나요? 계정·비밀번호는 보내지 마세요.", "public_analysis_consent")
    if "carousel" in supported:
        if not request["content_type"]:
            ask("CONTENT_TYPE_NEEDED", "표시하고 싶은 대상은 의료진·진료과목·제품·시공 사례 등 무엇인가요?", "content_type")
        if notes.get("search_result_type") not in {"carousel", "sitelinks", "place", "ad"}:
            ask("RESULT_TYPE_REVIEW", "참고 검색 화면이 일반 캐러셀·사이트링크·플레이스·광고 중 무엇인지 담당자가 자료를 검토하고 근거를 기록해 주세요.", "reference_result", "internal")
        elif notes["search_result_type"] != "carousel" and len(supported) > 1:
            ask("RESULT_SCOPE_MISMATCH", "담당자 검토상 참고 화면은 일반 캐러셀과 다릅니다. 원하는 결과와 견적 범위를 다시 협의해 주세요.", "reference_result")
    if request["content_available"] != "yes":
        ask("CONTENT_NEEDED", "대상 페이지에 필요한 실제 콘텐츠가 모두 있는지, 누락분을 누가 제공할지 알려주세요.", "content_available")
    if any(s in supported for s in ("carousel", "images")):
        if request["images_available"] != "yes":
            ask("IMAGES_NEEDED", "대상 항목의 사진·원본 이미지를 보유하거나 전달할 수 있나요?", "images_available")
        if request["content_usage_rights"] != "yes":
            ask("CONTENT_RIGHTS_NEEDED", "게시할 콘텐츠·이미지의 사용 권한을 고객 측에서 확인해 주세요.", "content_usage_rights")
        if any(v in (request["industry"] or "").lower() for v in ("병원", "의원", "의료", "hospital")) and not request["content_review_owner"]:
            ask("CONTENT_REVIEW_OWNER", "의료 콘텐츠·사진의 사실관계와 게시 전 검토를 담당할 고객 측 역할을 알려주세요.", "content_review_owner")

    synthetic = is_synthetic(environment) or is_synthetic(metadata)
    known_cms = [] if synthetic else [i["name"] for i in environment["technologies"]["cms"] if i["name"] != "UNKNOWN" and i["evidence"]]
    declared = cms_key(request["reported_cms"])
    comparison = {"customer_reported": request["reported_cms"] or "UNKNOWN", "observed_cms": known_cms or ["UNKNOWN"],
                  "state": "UNVERIFIED", "note": "고객 진술과 공개 기술 단서는 별도 기록이며 서로 덮어쓰지 않습니다."}
    if synthetic:
        comparison["note"] += " 가상 기술명은 실제 관찰 단서와 대조하거나 환경 검증에 사용하지 않습니다."
    if declared and known_cms:
        comparison["state"] = "CONSISTENT_CLUES" if declared in known_cms else "DIFFERENT_CLUES"
        if comparison["state"] == "DIFFERENT_CLUES":
            ask("CMS_DIFFERENCE", "고객이 알려주신 구축 방식과 공개 CMS 단서가 다릅니다. 수정 담당자에게 현재 운영 환경을 확인해 주세요. 어느 쪽도 자동으로 정답 처리하지 않습니다.", "reported_cms")
    architecture = [] if synthetic else [i["name"] for category in ("frontend", "backend") for i in environment["technologies"][category]
                    if i["name"] in {"Next.js", "Express"} and i["evidence"]]
    custom = (declared == "CUSTOM" or notes.get("complex_environment") is True
              or (bool(architecture) and not known_cms)
              or any(name not in {"WordPress", "Imweb", "Cafe24"} for name in known_cms))
    if synthetic:
        ask("SYNTHETIC_ENVIRONMENT", "가상 테스트 결과만 연결되어 실제 고객 환경은 미검증입니다. 담당자가 동의와 대상 URL을 확인한 뒤 실제 관찰 결과를 별도로 확보해 주세요. 자동 요청하지 않습니다.", "environment", "internal")
    elif environment["status"] != "ok" or environment["errors"]:
        ask("ENVIRONMENT_UNAVAILABLE", "환경 분석이 완료되지 않았습니다. 오류·차단 사유와 분석 동의·공개 URL을 확인해 주세요.", "environment", "internal")
    elif not known_cms and not custom:
        ask("ENVIRONMENT_UNKNOWN", "공개 단서로 작업 환경을 식별하지 못했습니다. 고객이 기술명을 몰라도 괜찮습니다. 내부 담당자가 수정 담당자에게 가능한 작업 경로를 확인해 주세요.", "environment", "internal")
    freshness = analysis_age(environment, now)
    if freshness["freshness"] != "RECENT":
        ask("ENVIRONMENT_DATE", "저장된 분석이 30일을 넘었거나 분석 시각을 신뢰하기 어렵습니다. 변경 여부와 최신 분석 필요성을 담당자가 확인해 주세요. 자동 재요청은 하지 않습니다.", "environment.analyzed_at", "internal")

    reasons = []
    if unsupported and not supported:
        decision = "OUT_OF_SCOPE"
        reasons.append("명시된 요청 작업이 현재 제공 범위(캐러셀·SEO·이미지 최적화)에 포함되지 않습니다.")
    elif supported == ["carousel"] and notes.get("search_result_type") in {"sitelinks", "place", "ad"}:
        decision = "OUT_OF_SCOPE"
        reasons.append("담당자 검토 기록의 참고 화면은 일반 캐러셀이 아닙니다. 해당 검색 기능을 캐러셀 구현으로 제공할 수 있다고 약속하지 않습니다.")
    elif questions:
        decision = "NEED_INFO"
        reasons.append("추가 확인이 필요한 항목이 있어 견적 범위를 확정하지 않았습니다.")
    elif custom:
        decision = "CUSTOM_QUOTE"
        reasons.append("고객의 자체 개발 진술·담당자 복잡성 검토 또는 프레임워크 빌드 단서에 따라 개별 기술 견적 검토가 필요합니다. 자체 개발 사실이나 배포 가능성을 자동 확정한 것은 아닙니다.")
    else:
        decision = "READY"
        reasons.append("사전 정보와 공개 환경 단서가 있어 견적 검토를 시작할 수 있습니다. 고객 진술의 권한은 미검증이며 계약·수정·배포 승인은 별도입니다.")
    if comparison["state"] == "DIFFERENT_CLUES":
        reasons.append("고객 진술과 탐지 단서가 달라 추가 확인이 필요합니다.")
    if synthetic:
        reasons.append("가상 테스트 데이터이며 실제 고객 환경 검증은 완료되지 않았습니다.")
    if freshness["freshness"] != "RECENT":
        reasons.append("이전 분석을 재사용했거나 시점이 불명확합니다. 원본 분석 시점을 보고서에 보존했습니다.")
    return {"schema_version": "pre-review-1.0", "reviewed_at": now.isoformat(), "decision": decision,
            "reasons": reasons, "questions": questions, "environment_comparison": comparison,
            "analysis": {**metadata, **freshness, "synthetic": synthetic}, "operator_review": notes,
            "reference_receipt": {"screenshot_status": "LOCAL_FILE_PRESENT" if screenshot_files else "UNVERIFIED" if reference["screenshots"] or notes.get("screenshot_files") else "NOT_PROVIDED",
                                  "available_file_names": screenshot_files},
            "possible_now": POSSIBLE_WORK, "requires_additional_permission": PERMISSIONS,
            "limitations": LIMITS, "deployment_access": "NOT_VERIFIED", "search_display_guaranteed": False}
