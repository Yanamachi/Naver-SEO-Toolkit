"""Static Korean pre-quote report, reusing STEP 1.1 presentation helpers."""

import json

from .intake import SERVICES, private_copy
from .report import Entry, STYLE, h, is_synthetic, render_entry, result_state

DECISIONS = {"READY": "견적 검토 가능", "NEED_INFO": "고객 추가 정보 필요",
             "CUSTOM_QUOTE": "별도 기술 견적 필요", "OUT_OF_SCOPE": "현재 서비스 범위 밖"}


def render_project(project, intake, environment, review):
    project, intake, environment, review = private_copy([project, intake, environment, review])
    request = intake["request"]
    fields = [("업체명", request["company_name"]), ("업종", request["industry"]), ("홈페이지", request["site_url"]),
              ("요청 작업", ", ".join(SERVICES.get(s, s) for s in request["requested_services"])),
              ("원하는 검색어", ", ".join(request["target_queries"])), ("캐러셀 대상", request["content_type"]),
              ("대상 페이지", " / ".join(request["target_page_urls"])),
              ("콘텐츠 / 이미지 / 사용 권한", " / ".join(request[k] for k in ("content_available", "images_available", "content_usage_rights"))),
              ("수정 권한 보유자 (고객 진술)", request["modification_owner"]), ("수정 경로 (고객 진술)", request["modification_route"]),
              ("희망 일정", request["desired_schedule"]), ("추가 요청", request["additional_requests"]),
              ("공개 영역 분석 동의", {True: "동의", False: "동의하지 않음", None: "미확인"}[request["public_analysis_consent"]])]
    overview = "<dl>" + "".join(f"<dt>{label}</dt><dd>{h(value or '미확인')}</dd>" for label, value in fields) + "</dl>"

    def items(values):
        return "<ul>" + "".join("<li>" + h(value) + "</li>" for value in values) + "</ul>"

    internal_codes = {"RESULT_TYPE_REVIEW", "REFERENCE_RECEIPT_REVIEW", "SYNTHETIC_ENVIRONMENT", "ENVIRONMENT_DATE", "ENVIRONMENT_UNKNOWN", "ENVIRONMENT_UNAVAILABLE"}
    customer_questions = [q for q in review["questions"] if q.get("audience", "internal" if q["code"] in internal_codes else "customer") == "customer"]
    internal_tasks = [q for q in review["questions"] if q not in customer_questions]
    questions = items(q["question"] for q in customer_questions) if customer_questions else "<p>현재 고객에게 확인할 추가 질문은 없습니다.</p>"
    tasks = items(q["question"] for q in internal_tasks) if internal_tasks else "<p>현재 필수 내부 검토 작업은 없습니다.</p>"
    comparison = review["environment_comparison"]
    reference = request["reference_result"]
    notes = review["operator_review"]
    analysis = review["analysis"]
    synthetic = is_synthetic(environment) or is_synthetic(analysis) or analysis.get("synthetic") is True
    sample_notice = ('<aside class="notice synthetic-warning" role="note"><strong>가상 테스트 탐지 데이터 · 실제 고객 환경 미검증</strong><p>기술명·근거·신뢰도는 테스트용 예시입니다. 실제 HTTP 분석이나 운영 환경 검증이 완료된 결과로 해석하지 마세요.</p></aside>' if synthetic else "")
    acquisition = {"REUSED": "기존 결과 재사용 · 사이트 재요청 없음", "LIVE": "동의 확인 후 신규 공개 영역 분석",
                   "NOT_REQUESTED": "새 분석 미실행"}.get(analysis["acquisition"], "분석 경로 미확인")
    freshness = {"RECENT": "최근 30일 이내", "STALE": "30일 초과 · 변경 여부 확인 필요", "FUTURE": "미래 시각 · 확인 필요", "UNKNOWN": "분석 시각 미확인"}[analysis["freshness"]]
    comparison_label = {"UNVERIFIED": "대조 가능한 정보 부족", "CONSISTENT_CLUES": "진술과 공개 단서가 부합 · 확정 아님",
                        "DIFFERENT_CLUES": "서로 다른 단서 · 담당자 확인 필요"}[comparison["state"]]
    screen_type = {None: "미검토", "unknown": "미검토", "carousel": "일반 캐러셀", "sitelinks": "사이트링크", "place": "플레이스", "ad": "광고"}[notes.get("search_result_type")]
    receipt = review.get("reference_receipt", {})
    receipt_label = {"LOCAL_FILE_PRESENT": "담당자가 지정한 로컬 실파일 존재 확인 · 내용과 진위는 별도 검토",
                     "UNVERIFIED": "미확인 · 자료명이나 경로만으로 확보 완료 처리하지 않음",
                     "NOT_PROVIDED": "실파일 미제공"}.get(receipt.get("screenshot_status"), "미확인 · 실파일 확인 기록 없음")
    environment_html = render_entry(Entry("환경 탐지 결과 · 고객 진술과 별도 보관", environment, result_state(environment)), 1, synthetic=synthetic)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>고객 프로젝트 사전 검토</title><style>{STYLE}dl{{grid-template-columns:220px 1fr}}p,li{{overflow-wrap:anywhere}}@media(max-width:600px){{dl{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><div class="eyebrow">NAVER SEO TOOLKIT · STEP 2</div><h1>고객 의뢰 사전 검토 보고서</h1><p>작업 ID: {h(project['job_id'])}</p><p class="muted">접수: {h(project['created_at'])} · 검토: {h(review['reviewed_at'])}</p></header>
{sample_notice}
<aside class="notice"><strong>{h(review['decision'])} · {DECISIONS[review['decision']]}</strong>{items(review['reasons'])}<p>READY는 견적 검토용입니다. 수정 권한·배포 가능성·네이버 노출을 확정하지 않습니다. 현재 단계에서는 운영 사이트를 변경하지 않습니다.</p></aside>
<section class="card"><h2>1. 고객 의뢰 및 요청 범위</h2>{overview}<p class="muted">yes=보유/확인 진술 · no=없음/미동의 · partial=일부 · unknown=미확인. 모두 고객이 제공한 정보이며 실제 권한 검증과 다릅니다.</p></section>
<section class="card"><h2>2. 고객 진술과 확인된 단서</h2><p>고객이 알고 있는 구축 방식: <strong>{h(comparison['customer_reported'])}</strong></p><p>공개 CMS 단서: <strong>{h(', '.join(comparison['observed_cms']))}</strong></p><p>대조 상태: {h(comparison_label)} · {h(comparison['note'])}</p><p>분석 연결 방식: {h(acquisition)} · 원본 파일: {h(analysis.get('source_filename') or '없음')}</p><p>원본 분석 시각: {h(analysis.get('analyzed_at') or 'UNKNOWN')} · 경과 일수: {h(analysis.get('age_days') if analysis.get('age_days') is not None else '미확인')} · 최신성: {h(freshness)}</p><p>데이터 출처: {h(analysis.get('data_origin', '관찰 결과 또는 미분석 기록'))}</p><p>과거 결과를 최신 분석으로 바꾸어 표시하지 않습니다. 캐러셀·사이트링크·플레이스·광고를 URL만으로 분류하지 않습니다.</p></section>
{environment_html}
<section class="card"><h2>3. 원하는 검색 화면과 담당자 검토</h2><p>기기: {h(reference['device'] or '미확인')} · 고객 설명: {h(reference['description'] or '미기재')}</p><p>참고 URL: {h(' / '.join(reference['urls']) or '없음')}</p><p>스크린샷 자료명: {h(' / '.join(reference['screenshots']) or '없음')} (자동 열기·판독 없음)</p><p>스크린샷 실파일 확보: {h(receipt_label)}</p><p>확인된 로컬 파일명: {h(' / '.join(receipt.get('available_file_names', [])) or '없음')}</p><p>담당자 기록의 화면 유형: {h(screen_type)}</p><p>검토 역할: {h(notes.get('reviewer_role') or '미기재')} · 기록된 근거: {h(notes.get('evidence') or '없음')}</p><p>담당자 기록은 별도 사람의 검토 진술이며 프로그램이 검색 화면의 진위를 검증한 결과가 아닙니다.</p></section>
<section class="card"><h2>4. 누락 정보 및 추가 질문</h2><h3>고객에게 확인할 질문 ({len(customer_questions)}개)</h3><div class="customer-questions">{questions}</div><h3>내부 담당자 검토 작업 ({len(internal_tasks)}개)</h3><div class="internal-tasks">{tasks}</div></section>
<section class="card"><h2>5. 현재 가능한 작업</h2>{items(review['possible_now'])}<h3>추가 권한·승인이 필요한 작업</h3>{items(review['requires_additional_permission'])}</section>
<section class="card"><h2>6. 자동 판단의 한계</h2>{items(review['limitations'])}<details><summary>마스킹된 정규화 의뢰 정보</summary><pre>{h(json.dumps(intake, ensure_ascii=False, indent=2))}</pre></details></section>
</main></body></html>'''
