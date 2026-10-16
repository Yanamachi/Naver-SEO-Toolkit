"""Normalize the existing customer form without demanding technical knowledge."""

from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl

import httpx

from .redact import MASK, SENSITIVE, redact
from .safety import DetectorError, public_ip, validate_url

SERVICES = {"carousel": "네이버 캐러셀", "seo": "SEO", "images": "이미지 최적화"}
SERVICE_ALIASES = {**{k: k for k in SERVICES}, **{v.lower(): k for k, v in SERVICES.items()},
                   "검색 노출 문제 진단": "seo", "기존 검색 노출 문제 진단": "seo"}
UNKNOWN_WORDS = {"", "unknown", "모름", "잘 모름", "확인 필요", "미정"}


class IntakeError(ValueError):
    """Expected local input/storage error, with a non-sensitive explanation."""


def private_copy(value):
    """Mask known credentials/contacts before persisting or presenting intake."""
    if isinstance(value, dict):
        return {key: private_copy(item) for key, item in redact(value).items()}
    if isinstance(value, list):
        return [private_copy(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", MASK, value, flags=re.S)
        value = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_MASKED]", value)
        value = re.sub(r"(?<![\w-])(?:0(?:1[016789]|2|[3-6]\d)|\+82[- .]?0?(?:1[016789]|2|[3-6]\d))[- .]?\d{3,4}[- .]?\d{4}(?!\d)", "[PHONE_MASKED]", value)
        return redact(value)
    return value


def read_object(path: Path) -> dict:
    try:
        if path.is_symlink():
            raise IntakeError("심볼릭 링크 입력은 허용하지 않습니다.")
        with path.open("rb") as handle:
            raw = handle.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise IntakeError("입력 파일은 5 MiB 이하로 작성하세요.")
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise IntakeError("입력은 JSON 객체여야 합니다.")
        return data
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise IntakeError("JSON 객체를 읽지 못했습니다. 경로·UTF-8·형식·5 MiB 제한을 확인하세요.") from exc


def safe_url(value: str) -> str:
    """Syntax/literal-IP check only. Offline normalization never performs DNS."""
    url = validate_url(value)
    if any(SENSITIVE.search(key) for key, _ in parse_qsl(url.query.decode("ascii"), keep_blank_values=True)):
        raise DetectorError("UNSAFE_URL", "인증정보가 포함된 URL은 공개 영역 분석에 사용할 수 없습니다.")
    try:
        address = ipaddress.ip_address(url.host)
    except ValueError:
        pass
    else:
        if not public_ip(str(address)):
            raise DetectorError("UNSAFE_DESTINATION", "공개 웹사이트 URL이 필요합니다.")
    return str(url)


@dataclass
class Intake:
    document: dict
    site_url: str | None  # Original validated URL is ephemeral, never logged.


def normalize(data: dict) -> Intake:
    issues = []

    def text(key, source=None):
        value = (data if source is None else source).get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            issues.append({"code": "INVALID_FIELD", "field": key, "question": f"{key} 항목은 문자열로 다시 알려주세요."})
            return None
        return None if value.strip().lower() in UNKNOWN_WORDS else value.strip()

    def strings(key, source=None):
        value = (data if source is None else source).get(key, [])
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            issues.append({"code": "INVALID_FIELD", "field": key, "question": f"{key} 항목을 문자열 배열로 알려주세요."})
            return []
        return list(dict.fromkeys(v.strip() for v in value if v.strip().lower() not in UNKNOWN_WORDS))

    def availability(key):
        value = data.get(key)
        if value is True:
            return "yes"
        if value is False:
            return "no"
        aliases = {"yes": "yes", "있음": "yes", "예": "yes", "보유": "yes", "확인 완료": "yes", "no": "no", "없음": "no",
                   "아니요": "no", "partial": "partial", "일부": "partial", "일부만 있음": "partial", "대부분 있음": "partial",
                   "별도 전달 가능": "yes", "새로 제작 필요": "no"}
        if value is None or (isinstance(value, str) and value.strip().lower() in UNKNOWN_WORDS):
            return "unknown"
        if isinstance(value, str) and value.strip().lower() in aliases:
            return aliases[value.strip().lower()]
        issues.append({"code": "INVALID_FIELD", "field": key, "question": f"{key}의 보유/확인 여부를 yes/no/partial/unknown으로 알려주세요."})
        return "unknown"

    request = {key: text(key) for key in (
        "company_name", "industry", "site_url", "reported_cms", "content_type", "modification_owner",
        "modification_route", "desired_schedule", "additional_requests", "content_review_owner",
    )}
    site_url = None
    if request["site_url"]:
        try:
            site_url = safe_url(request["site_url"])
            request["site_url"] = site_url
        except (DetectorError, ValueError):
            issues.append({"code": "INVALID_SITE_URL", "field": "site_url", "question": "공개 웹사이트의 올바른 HTTP(S) 홈페이지 URL을 알려주세요. 내부망·인증정보 포함 URL은 분석하지 않습니다."})
    services = strings("requested_services")
    request["requested_services"] = list(dict.fromkeys(SERVICE_ALIASES.get(v.lower(), v) for v in services))
    request["target_queries"] = strings("target_queries")
    request["target_page_urls"] = strings("target_page_urls")
    reference = data.get("reference_result", {})
    if not isinstance(reference, dict):
        issues.append({"code": "INVALID_FIELD", "field": "reference_result", "question": "검색 결과 참고 자료를 urls/screenshots/device/description 객체로 정리해 주세요."})
        reference = {}
    request["reference_result"] = {"urls": strings("urls", reference), "screenshots": strings("screenshots", reference),
                                   "device": text("device", reference), "description": text("description", reference)}
    for key in ("content_available", "images_available", "content_usage_rights"):
        request[key] = availability(key)
    consent = data.get("public_analysis_consent")
    request["public_analysis_consent"] = consent if isinstance(consent, bool) else None
    if consent is not None and not isinstance(consent, bool):
        issues.append({"code": "INVALID_CONSENT", "field": "public_analysis_consent", "question": "공개 영역 분석 동의 여부를 JSON true/false로 명시해 주세요. 문자열은 동의로 인정하지 않습니다."})
    for key, values in (("target_page_urls", request["target_page_urls"]), ("reference_result.urls", request["reference_result"]["urls"])):
        for value in values:
            try:
                checked = safe_url(value)
                if key == "target_page_urls" and site_url and httpx.URL(checked).host != httpx.URL(site_url).host:
                    issues.append({"code": "TARGET_SCOPE", "field": key, "question": "대상 페이지가 홈페이지와 다른 호스트입니다. 작업 대상과 승인 범위를 확인해 주세요. 대상 페이지를 자동 요청하지 않습니다."})
            except (DetectorError, ValueError):
                issues.append({"code": "INVALID_PAGE_URL", "field": key, "question": "대상 페이지와 참고 URL에 올바른 공개 HTTP(S) 주소를 적어주세요."})
                break
    return Intake(private_copy({"schema_version": "intake-1.0", "source_template": "templates/01_customer_inquiry_quote.md",
                                "request": request, "validation_issues": issues}), site_url)


def normalize_notes(data: dict) -> dict:
    """Operator records stay separate from customer claims and observed facts."""
    result = {key: data.get(key) for key in ("reviewer_role", "evidence", "search_result_type", "complex_environment")}
    files = data.get("screenshot_files", [])
    if not isinstance(files, list) or any(not isinstance(value, str) for value in files):
        raise IntakeError("담당자가 확보한 screenshot_files는 로컬 절대 경로 문자열 배열이어야 합니다.")
    result["screenshot_files"] = files
    if any(result[key] is not None and not isinstance(result[key], str) for key in ("reviewer_role", "evidence", "search_result_type")):
        raise IntakeError("담당자 검토의 역할·근거·화면 유형은 문자열이어야 합니다.")
    if result["search_result_type"] not in {None, "unknown", "carousel", "sitelinks", "place", "ad"}:
        raise IntakeError("담당자 화면 유형은 unknown/carousel/sitelinks/place/ad 중 하나입니다.")
    if result["complex_environment"] is not None and not isinstance(result["complex_environment"], bool):
        raise IntakeError("complex_environment는 true/false여야 합니다.")
    if result["search_result_type"] not in {None, "unknown"} or result["complex_environment"] is True or files:
        if not all(isinstance(result[key], str) and result[key].strip().lower() not in UNKNOWN_WORDS for key in ("reviewer_role", "evidence")):
            raise IntakeError("담당자 판정에는 reviewer_role과 evidence를 함께 기록하세요.")
    return private_copy(result)


def available_screenshots(notes: dict) -> list[str]:
    """Check operator-designated local files only; never open images or URLs."""
    available = []
    for value in notes.get("screenshot_files", []):
        if value.startswith(("\\", "//")):
            continue  # UNC/device/network paths are not local attachment evidence.
        path = Path(value)
        if not path.is_absolute() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            continue
        try:
            if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (path, *path.parents)):
                continue
            if path.is_file() and path.stat().st_size > 0:
                available.append(path.name)
        except (OSError, ValueError):
            continue
    return list(dict.fromkeys(available))
