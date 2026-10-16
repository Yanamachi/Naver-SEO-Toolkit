"""Offline report of existing schema 1.0 results. No HTTP or DNS operations."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import json
import math
import os
from pathlib import Path
import tempfile

from .detect import CATEGORIES
from .redact import mask_text, redact

MAX_JSON_BYTES = 5 * 1024 * 1024
SECURITY_CODES = {"UNSAFE_URL", "UNSAFE_DESTINATION", "REDIRECT_SCOPE", "UNSAFE_REDIRECT"}
LABELS = {"cms": "CMS", "frontend": "프런트엔드", "backend": "백엔드",
          "server": "HTTP 응답 서버 (공개 표기)", "cdn": "CDN (기존 탐지 결과)"}
STATES = {"ok": "단서 있음", "unknown": "기술 미확인", "error": "분석 오류",
          "blocked": "보안 차단", "input_error": "JSON 입력 오류"}
RULE_NOTES = {
    "wordpress_generator": "generator에서 WordPress 표기 확인. 실제 서버 런타임은 미검증입니다.",
    "wordpress_assets": "WordPress 자원 경로가 있습니다. 정적 복사본이나 외부 자원일 수 있습니다.",
    "imweb_assets": "아임웹 자원만 확인했습니다. 자원 개수가 늘어도 플랫폼 확정 근거가 되지 않습니다.",
    "cafe24_assets": "카페24 자원만 확인했습니다. 자원 개수가 늘어도 플랫폼 확정 근거가 되지 않습니다.",
    "next_assets": "Next.js 빌드 자원이 있습니다. React·Node.js 런타임은 추정하지 않습니다.",
    "next_header": "응답 헤더에서 Next.js 표기 확인. 헤더는 위장할 수 있습니다.",
    "express_header": "응답 헤더에서 Express 표기 확인. 서버 내부는 검증하지 않았습니다.",
    "php_header": "응답 헤더에서 PHP 표기 확인. 서버 내부는 검증하지 않았습니다.",
    "server_header": "응답자가 광고한 Server 값입니다. 프록시·엣지일 수 있어 원본 서버를 확정할 수 없습니다.",
    "cloudflare_ray": "Cloudflare 응답 마커가 있습니다. 원본 서버 기술은 알 수 없습니다.",
}


@dataclass
class Entry:
    filename: str
    data: dict
    state: str


def validate_result(data):
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("지원하는 schema_version은 1.0입니다.")
    if data.get("status") not in {"ok", "error"} or not isinstance(data.get("request_url"), str):
        raise ValueError("status 또는 request_url 형식이 잘못되었습니다.")
    technologies = data.get("technologies")
    if not isinstance(technologies, dict):
        raise ValueError("technologies 객체가 필요합니다.")
    for category in CATEGORIES:
        items = technologies.get(category)
        if not isinstance(items, list) or not items:
            raise ValueError("기술 범주별 결과 배열이 필요합니다.")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("기술 이름 형식이 잘못되었습니다.")
            score = item.get("confidence")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("신뢰도는 0~1 사이 유한한 숫자여야 합니다.")
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or any(not isinstance(e, dict) for e in evidence):
                raise ValueError("evidence 객체 배열이 필요합니다.")
            for e in evidence:
                if any(not isinstance(e.get(key), str) for key in ("rule", "source", "value", "meaning", "reference")):
                    raise ValueError("근거 필드에는 문자열이 필요합니다.")
    errors = data.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(e, dict) or not isinstance(e.get("code"), str) or not isinstance(e.get("message"), str)
        for e in errors
    ):
        raise ValueError("errors 형식이 잘못되었습니다.")


def result_state(data: dict) -> str:
    if any(error["code"] in SECURITY_CODES for error in data["errors"]):
        return "blocked"
    if data["status"] == "error" or data["errors"]:
        return "error"
    if all(item["name"] == "UNKNOWN" for category in ("cms", "frontend", "backend")
           for item in data["technologies"][category]):
        return "unknown"
    return "ok"


def load_entries(source: Path) -> list[Entry]:
    if source.is_dir():
        paths = sorted((p for p in source.iterdir() if p.suffix.lower() == ".json" and p.is_file()), key=lambda p: p.name.lower())
    elif source.is_file() and source.suffix.lower() == ".json":
        paths = [source]
    else:
        raise ValueError("JSON 파일 또는 JSON이 있는 폴더를 입력하세요.")
    if not paths:
        raise ValueError("입력 폴더에 JSON 파일이 없습니다.")
    entries = []
    for path in paths:
        try:
            if path.is_symlink():
                raise ValueError("심볼릭 링크 JSON은 읽지 않습니다.")
            with path.open("rb") as handle:
                content = handle.read(MAX_JSON_BYTES + 1)
            if len(content) > MAX_JSON_BYTES:
                raise ValueError("JSON 파일은 최대 5 MiB까지 읽습니다.")
            data = json.loads(content.decode("utf-8-sig"))
            validate_result(data)
            entries.append(Entry(mask_text(path.name), redact(data), result_state(data)))
        except (OSError, UnicodeError, ValueError, RecursionError, TypeError):
            # Do not reflect parser exceptions: they may quote private input values.
            entries.append(Entry(mask_text(path.name), {"errors": [{"code": "INPUT_ERROR",
                "message": "JSON을 읽거나 검증하지 못했습니다. UTF-8, 스키마 1.0, 형식 및 5 MiB 제한을 확인하세요."}]}, "input_error"))
    return entries


def assessment(category: str, item: dict) -> tuple[str, str]:
    if item["name"] == "UNKNOWN":
        return "UNKNOWN", "공개 단서로 식별하지 못했습니다. 기술이 없다는 뜻이 아닙니다."
    rules = {e["rule"] for e in item["evidence"]}
    if not rules:
        return "근거 부족 · 미확정", "기술 이름은 기록되어 있으나 저장된 근거가 없습니다."
    if category == "cms" and item["name"].lower() in {"imweb", "cafe24"}:
        return "후보 · 미확정", "외부 자원만으로 플랫폼을 확정하지 않습니다. 신뢰도나 자원 수만으로 승격하지 않습니다."
    if category == "server":
        return "공개 표기 확인", RULE_NOTES["server_header"]
    if "wordpress_generator" in rules and item["name"] == "WordPress":
        return "명시 표기 확인", RULE_NOTES["wordpress_generator"]
    if "next_assets" in rules and item["name"] == "Next.js":
        return "빌드 자원 확인", RULE_NOTES["next_assets"]
    if rules & {"next_header", "express_header", "php_header", "cloudflare_ray"}:
        return "공개 마커 확인", "기록된 응답 표기를 확인했습니다. 실제 내부 운영 환경을 확정하지 않습니다."
    return "후보 · 미확정", "기록된 자원 또는 단서를 확인했습니다. 플랫폼·서버 내부 환경은 미검증입니다."


def terminal_summary(entries: list[Entry]) -> str:
    counts = Counter(entry.state for entry in entries)
    lines = [f"총 {len(entries)}개 JSON | " + " · ".join(f"{label} {counts[key]}" for key, label in STATES.items())]
    for entry in entries:
        parts = []
        synthetic = is_synthetic(entry.data)
        if entry.state != "input_error":
            for category in ("cms", "frontend", "backend", "server", "cdn"):
                parts.append(LABELS[category] + ": " + ", ".join(
                    f"{item['name']} ({'가상 예시 · 실제 미검증' if synthetic else assessment(category, item)[0]})" for item in entry.data["technologies"][category]))
        codes = ", ".join(e["code"] for e in entry.data["errors"])
        if codes and parts:
            parts.append("오류 코드: " + codes)
        label = "가상 테스트 데이터" if synthetic else STATES[entry.state]
        lines.append(f"[{label}] {entry.filename} | " + " | ".join(parts or [codes]))
    if any(is_synthetic(entry.data) for entry in entries):
        lines.append("가상 항목의 저장 상태 집계는 실제 고객 환경의 검증 완료 건수가 아닙니다.")
    return "\n".join(lines)


def h(value) -> str:
    return escape(str(value), quote=True)


def is_synthetic(data: dict) -> bool:
    origin = data.get("data_origin")
    return isinstance(origin, str) and origin.startswith("SYNTHETIC_TEST_FIXTURE")


def render_item(category: str, item: dict, *, synthetic=False) -> str:
    label, note = assessment(category, item)
    evidence = item["evidence"]
    score = f"규칙 신뢰도 {item['confidence']:.2f}"
    if synthetic:
        label = "가상 예시 · 실제 검증 아님"
        note = "테스트용 기술명·근거이며 실제 고객 환경에서 관찰한 결과가 아닙니다."
        score = "신뢰도는 가상 예제 값 · 실제 평가에 사용하지 않음"
    summary = " / ".join(dict.fromkeys(RULE_NOTES.get(e["rule"], "추가 규칙: 전체 근거를 확인하세요.") for e in evidence))
    details = ""
    if evidence:
        rows = "".join("<tr>" + "".join(f"<td>{h(e[key])}</td>" for key in
                        ("rule", "source", "value", "meaning", "reference")) + "</tr>" for e in evidence)
        details = f'<details><summary>전체 근거 펼쳐보기 ({len(evidence)}개)</summary><div class="scroll"><table><thead><tr><th>규칙</th><th>관찰 위치</th><th>관찰 값</th><th>원문 설명</th><th>참고 자료 (텍스트)</th></tr></thead><tbody>{rows}</tbody></table></div></details>'
    if synthetic:
        summary = "아래 근거는 가상 입력 원문입니다. 실제 기술 확인 근거로 사용하지 않습니다."
    return f'<div class="technology"><strong>{h(item["name"])}</strong> <span class="tag">{h(label)}</span><span class="score">{h(score)}</span><p>{h(note)}</p><p class="muted">{h(summary)}</p>{details}</div>'


def render_entry(entry: Entry, index: int, *, synthetic=False) -> str:
    data = entry.data
    synthetic = synthetic or is_synthetic(data)
    body = "".join(f'<p class="error"><strong>{h(e["code"])}</strong> {h(e["message"])}</p>' for e in data["errors"])
    if entry.state != "input_error":
        body += f'<dl><dt>입력 URL</dt><dd>{h(data["request_url"])}</dd><dt>최종 URL</dt><dd>{h(data.get("final_url") or "UNKNOWN")}</dd><dt>원본 분석 시각</dt><dd>{h(data.get("analyzed_at", "UNKNOWN"))}</dd></dl>'
        if entry.state in {"blocked", "error"}:
            body += '<p class="notice">분석이 완료되지 않았습니다. UNKNOWN을 기술 부재로 해석하지 마세요.</p>'
        for category in CATEGORIES:
            body += f'<h3>{LABELS[category]}</h3>' + "".join(render_item(category, item, synthetic=synthetic) for item in data["technologies"][category])
        body += '<h3>원본 서버 · 자체 개발 여부</h3><p>원본 서버: <strong>UNKNOWN</strong> · 자체 개발 여부: <strong>UNKNOWN</strong><br>저장된 공개 단서만으로 내부 환경을 확정하지 않습니다.</p>'
        json_label = "가상 원본 JSON 보기 · 신뢰도 수치는 테스트 값" if synthetic else "마스킹된 전체 JSON 보기"
        body += f'<details><summary>{json_label}</summary><pre>{h(json.dumps(data, ensure_ascii=False, indent=2))}</pre></details>'
    state_class, state_label = ("blocked", "가상 데이터 · 실제 환경 미검증") if synthetic else (entry.state, STATES[entry.state])
    return f'<section id="result-{index}" class="card"><div class="section-head"><h2>{h(entry.filename)}</h2><span class="state {state_class}">{state_label}</span></div>{body}</section>'


STYLE = """
:root{color-scheme:light;font-family:system-ui,'Malgun Gothic',sans-serif;color:#172b40;background:#f2f5f8;line-height:1.65}
body{margin:0} main{max-width:1180px;margin:auto;padding:40px 24px 64px}h1{font-size:2rem;margin:6px 0}h2{font-size:1.35rem;margin:0}h3{margin:26px 0 8px;font-size:1rem}p{margin:8px 0} .eyebrow{color:#236458;font-weight:700;letter-spacing:.08em;font-size:.8rem}
.muted,.score{color:#526579;font-size:.9rem}.notice{background:#e8f1fa;border-left:4px solid #416f9e;padding:14px 18px;margin:20px 0}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}.stat{background:white;padding:16px 22px;border:1px solid #dce3eb;border-radius:10px;flex:1;min-width:110px}.stat strong{display:block;font-size:1.8rem}.card{background:white;border:1px solid #dce3eb;border-radius:12px;margin:24px 0;padding:26px}.section-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}.tag,.state{border-radius:5px;padding:3px 8px;background:#edf1f5;font-size:.85rem;display:inline-block}.ok{background:#dcefe7;color:#18533f}.unknown{background:#edf1f5}.blocked{background:#fff0ce;color:#704d00}.error,.input_error{background:#fde6e7;color:#8a2330}.error{padding:10px}.score{margin-left:10px}.technology{border-left:3px solid #dce3eb;padding:8px 0 8px 16px;margin:12px 0}details{margin-top:12px}summary{cursor:pointer;color:#245f90;font-weight:600;padding:6px 0}table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dce3eb;padding:10px;min-width:110px;overflow-wrap:anywhere}th{background:#f2f5f8}.scroll{overflow-x:auto}td:nth-child(3){min-width:240px}dl{display:grid;grid-template-columns:130px 1fr;gap:6px;margin:20px 0}dt{color:#526579}dd{margin:0;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem;background:#f2f5f8;padding:16px}a{color:#245f90}nav{display:flex;gap:12px;flex-wrap:wrap}h2,strong{overflow-wrap:anywhere}@media(max-width:600px){main{padding:24px 12px}.card{padding:18px}dl{grid-template-columns:1fr}.score{display:block;margin:4px 0}}@media print{body{background:white}main{max-width:none}.card{break-inside:avoid}details{display:block}nav{display:none}}
"""


def render_report(entries: list[Entry]) -> str:
    counts = Counter(entry.state for entry in entries)
    stats = "".join(f'<div class="stat"><strong>{counts[key]}</strong>{label}</div>' for key, label in STATES.items())
    nav = "".join(f'<a href="#result-{i}">{h(entry.filename)}</a>' for i, entry in enumerate(entries, 1))
    cards = "".join(render_entry(entry, i) for i, entry in enumerate(entries, 1))
    sample_count = sum(is_synthetic(entry.data) for entry in entries)
    sample_notice = (f'<aside class="notice synthetic-warning" role="note"><strong>가상 테스트 데이터 포함: {sample_count}개</strong><p>가상 기술명·근거·신뢰도는 실제 사이트 검증 결과가 아닙니다. 집계는 저장된 상태이며 가상 항목을 실제 환경 검증 완료로 해석하지 마세요.</p></aside>' if sample_count else "")
    overview_rows = []
    for entry in entries:
        cells = [entry.filename]
        for category in ("cms", "frontend", "server", "cdn"):
            items = entry.data.get("technologies", {}).get(category, [])
            cells.append(" / ".join(f"{item['name']} · {'가상 예시' if is_synthetic(entry.data) else assessment(category, item)[0]}"
                                    if item["name"] != "UNKNOWN" else "UNKNOWN" for item in items) or "UNKNOWN")
        cells.append("가상 데이터 · 미검증" if is_synthetic(entry.data) else STATES[entry.state])
        overview_rows.append("<tr>" + "".join(f"<td>{h(cell)}</td>" for cell in cells) + "</tr>")
    overview = '<div class="scroll"><table aria-label="파일별 종합 비교"><thead><tr><th>JSON 파일</th><th>CMS</th><th>프런트엔드</th><th>HTTP 응답 서버</th><th>CDN</th><th>분석 상태</th></tr></thead><tbody>' + "".join(overview_rows) + '</tbody></table></div>'
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>웹사이트 환경 분석 보고서</title><style>{STYLE}</style></head><body><main>
<header><div class="eyebrow">ENVIRONMENT DETECTOR · STEP 1.1</div><h1>웹사이트 환경 분석 보고서</h1><p>저장된 {len(entries)}개 JSON의 공개 기술 단서를 검토했습니다.</p><p class="muted">보고서 생성: {generated} (UTC) · 사이트 재요청 없음</p></header>
{sample_notice}<div class="stats">{stats}</div><aside class="notice"><strong>확인된 단서와 실제 운영 환경은 다릅니다.</strong><p>‘명시 표기 확인’은 저장된 헤더·메타 표기의 확인이며 플랫폼 확정이 아닙니다. 아임웹·카페24 자원은 후보로 유지합니다. 규칙 신뢰도는 확률이 아니며, 원본 서버와 자체 개발 여부는 UNKNOWN입니다.</p><p>‘기술 미확인’은 정상 응답에서 CMS·프런트엔드·백엔드를 식별하지 못한 상태입니다. HTTP 서버·CDN 단서는 별도로 표시합니다. 오류·보안 차단은 분석 미완료입니다.</p><p>전체 근거는 JSON에 저장된 범위입니다. URL 사용자 정보·쿼리·프래그먼트와 알려진 민감 키를 마스킹했습니다. 외부 자원·스크립트·폰트를 불러오지 않습니다.</p></aside>
<section class="card"><h2>파일별 종합 비교</h2>{overview}</section><nav aria-label="결과 바로가기">{nav}</nav>{cards}<footer class="muted">중복 사이트 결과도 파일별로 보존합니다. 원본 JSON과 기존 탐지 결과는 변경하지 않았습니다.</footer></main></body></html>'''


def save_report(output: Path, entries: list[Entry]) -> None:
    if output.suffix.lower() != ".html":
        raise ValueError("보고서 출력 확장자는 .html이어야 합니다. JSON 덮어쓰기는 허용하지 않습니다.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".report-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(render_report(entries))
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
