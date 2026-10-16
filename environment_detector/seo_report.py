"""Offline Korean SEO report using the existing report style and evidence UI."""

from collections import Counter
import json

from .intake import SERVICES, private_copy
from .report import Entry, STYLE, h, is_synthetic, render_entry, result_state

LABELS = {"PASS": "확인 범위 내 통과", "ISSUE": "개선 필요", "WARNING": "검토 권장", "NOT_VERIFIED": "미검증", "NOT_APPLICABLE": "해당 없음"}
SEVERITIES = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음", "INFO": "정보"}
PRIORITY = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
PAGE_STATES = {"ANALYZED": "초기 HTML 분석 완료", "HTTP_ERROR": "HTTP 오류·접근 차단", "NON_HTML": "HTML 검사 불가", "FETCH_FAILED": "요청 실패", "BLOCKED": "보안·정책 차단", "DUPLICATE_FINAL_URL": "동일 최종 URL 중복 제외", "NOT_VERIFIED": "미검증"}
AUDIT_STATES = {"COMPLETE": "정적 검사 완료", "PARTIAL": "일부 검사 미검증", "BLOCKED": "HTML 분석 불가·차단"}


def listing(values):
    return "<ul>" + "".join(f"<li>{h(str(v))}</li>" for v in values) + "</ul>"


def render_audit(project, intake, environment, audit):
    project, intake, environment, audit = private_copy([project, intake, environment, audit])
    request, summary = intake["request"], audit["summary"]
    sample = ('<aside class="notice synthetic-warning"><strong>가상 테스트 데이터 · 실제 고객 SEO 미검증</strong><p>가상 프로젝트 자료로 작성한 기능 검증용 보고서입니다. 실제 사이트 분석 결과로 사용하지 마세요.</p></aside>' if is_synthetic(audit) else "")
    synthetic_environment = is_synthetic(environment) or audit["environment_reference"].get("synthetic") is True
    environment_html = render_entry(Entry("기존 환경 탐지 결과 · 별도 시점의 참고 정보", environment, result_state(environment)), 1, synthetic=synthetic_environment)
    problems = sorted((f for f in audit["findings"] if f["result"] in {"ISSUE", "WARNING"}), key=lambda f: (PRIORITY.get(f["severity"], 4), f["result"] != "ISSUE"))
    priority_rows = "".join(f"<tr><td>{h(SEVERITIES.get(f['severity'], f['severity']))}</td><td>{h(LABELS[f['result']])}</td><td>{h(f['title'])}<br><small>{h(f['url'])}</small></td><td>{h(f['recommendation'])}</td></tr>" for f in problems)
    groups = {}
    for f in audit["findings"]:
        key = f["id"].split(".")[0]
        groups.setdefault(key, Counter())[f["result"]] += 1
    group_labels = {"http": "HTTP 응답", "robots": "접근·색인 정책", "title": "Title", "description": "Description", "canonical": "대표 URL", "og": "공유 정보", "lang": "문서 언어", "headings": "제목 구조", "links": "링크", "alt": "이미지 ALT", "sitemap": "사이트맵", "jsonld": "기존 구조화 데이터", "rendering": "렌더링 검사 범위", "scope": "승인·보안 범위"}
    group_rows = "".join(f"<tr><td>{h(group_labels.get(k, k))}</td>" + "".join(f"<td>{counts[s]}</td>" for s in LABELS) + "</tr>" for k, counts in groups.items())
    details = []
    for f in audit["findings"]:
        # Official reference links are fixed code-owned values in generated JSON.
        # A manually edited JSON cannot turn them into javascript:/data: links.
        refs = " · ".join(f'<a href="{h(link)}" rel="noreferrer">공식 문서</a>' for link in f["documentation"] if isinstance(link, str) and link.startswith("https://"))
        details.append(f'''<details class="card"><summary>{h(LABELS[f['result']])} · {h(SEVERITIES[f['severity']])} · {h(f['title'])}</summary><p>검사 ID: {h(f['id'])}<br>URL: {h(f['url'])}</p><p><strong>판단 이유:</strong> {h(f['reason'])}</p><p><strong>개선 권고:</strong> {h(f['recommendation'])}</p><h4>실제 관찰 근거</h4><pre>{h(json.dumps(f['evidence'], ensure_ascii=False, indent=2))}</pre><p>{refs}</p></details>''')
    unverified = [f"{f['title']} · {f['url']}" for f in audit["findings"] if f["result"] == "NOT_VERIFIED"]
    page_rows = "".join(f"<tr><td>{h(p['request_url'])}<br><small>최종: {h(p.get('final_url') or '미접근')}</small></td><td>{h(PAGE_STATES.get(p['state'], p['state']))}</td><td>{h(str((p.get('http') or {}).get('status_code', (p.get('error') or {}).get('code', '미검증'))))}</td></tr>" for p in audit["pages"])
    cms = [t["name"] for t in environment["technologies"]["cms"] if t["name"] != "UNKNOWN"]
    reference = "고객 진술과 공개 기술 단서를 대조한 뒤 담당자가 편집·승인 경로를 확인해야 합니다. UNKNOWN이나 가상 환경에서 수정 방법을 확정하지 않습니다."
    if not synthetic_environment:
        if "WordPress" in cms:
            reference += " WordPress 단서가 있으면 기존 SEO 플러그인 출력과 테마의 메타데이터 중복을 담당자가 확인할 수 있습니다."
        if any(name in cms for name in ("Imweb", "Cafe24")):
            reference += " 호스팅형 CMS 단서는 후보일 수 있습니다. 제공되는 SEO 설정 범위를 운영 담당자가 확인해야 합니다."
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>SEO 읽기 전용 분석 보고서</title><style>{STYLE}p,li{{overflow-wrap:anywhere}}summary{{cursor:pointer}}table{{width:100%}}.table-scroll{{overflow:auto}}</style></head><body><main>
<header><div class="eyebrow">NAVER SEO TOOLKIT · STEP 3</div><h1>SEO 사전 분석 보고서</h1><p>{h(request.get('company_name') or '업체명 미확인')} · {h(project['job_id'])}</p><p>{h(request.get('site_url') or 'URL 미확인')}</p><p>분석 시각: {h(audit['analyzed_at'])} · 상태: {h(AUDIT_STATES.get(audit['status'], audit['status']))} ({h(audit['status'])})</p></header>{sample}
<aside class="notice"><strong>영업 담당자 요약</strong><p>분석한 HTML 페이지 {summary['analyzed_pages']}개 · 실패·차단·비HTML {summary['failed_pages']}개 · GET {summary['request_count']}회</p><p>개선 필요 {summary['results'].get('ISSUE', 0)}건 · 검토 권장 {summary['results'].get('WARNING', 0)}건 · 미검증 {summary['results'].get('NOT_VERIFIED', 0)}건</p><p>진단 건수는 검사 항목 수이며 페이지 수와 다릅니다. 통과는 해당 정적 검사 범위에만 적용됩니다. 운영 사이트는 변경하지 않았습니다.</p></aside>
<section class="card"><h2>1. 고객 요청과 분석 범위</h2><p>요청 작업: {h(', '.join(SERVICES.get(s, s) for s in request.get('requested_services', [])))}</p><p>고객이 알고 있는 환경: {h(request.get('reported_cms') or '미확인')} (고객 진술)</p><p>대상: {h(' / '.join(audit['scope']['explicit_urls']))}</p><p>내부 탐색 승인: {h(str(audit['scope']['crawl_approved']))} · 사이트맵 검사 승인: {h(str(audit['scope']['sitemaps_approved']))} · 최대 {audit['options']['max_pages']}페이지</p><p>색인 의도: {h(audit['options']['indexing_goal'])} · 의뢰에 없는 의도를 자동 추정하지 않습니다.</p><div class="table-scroll"><table><thead><tr><th>요청 / 최종 URL</th><th>처리 상태</th><th>HTTP / 사유</th></tr></thead><tbody>{page_rows}</tbody></table></div></section>
<section class="card"><h2>2. 기술 환경 참고 정보</h2><p>환경 분석 시점: {h(environment.get('analyzed_at') or '미확인')} · 이번 SEO 실행으로 갱신하지 않음</p><p>{h(reference)}</p></section>{environment_html}
<section class="card"><h2>3. 항목별 검사 요약</h2><div class="table-scroll"><table><thead><tr><th>항목</th>{''.join('<th>' + h(v) + '</th>' for v in LABELS.values())}</tr></thead><tbody>{group_rows}</tbody></table></div></section>
<section class="card"><h2>4. 우선순위별 검토 · 영업 담당자용</h2><div class="table-scroll"><table><thead><tr><th>중요도</th><th>판정</th><th>문제와 URL</th><th>다음 작업</th></tr></thead><tbody>{priority_rows}</tbody></table></div><p>색인 목적·장식 이미지·대표 URL 운영 의도에 따라 권고를 조정해야 합니다. 수정 권한·비용·효과를 자동 확정하지 않습니다.</p></section>
<section class="card"><h2>5. 직접 확인하지 못한 항목</h2>{listing(unverified)}{listing(audit['limitations'])}</section>
<section class="card"><h2>6. 고객에게 추가 요청할 정보</h2>{listing(audit['customer_questions'])}<h3>내부 담당자 검토</h3><p>관찰 근거와 운영 의도를 대조하고, JavaScript 렌더링·실제 검색 상태·관리자 설정은 적절한 권한과 별도 승인으로 확인하세요.</p></section>
<section><h2>7. 기술 담당자용 전체 진단 근거</h2>{''.join(details)}<details class="card"><summary>마스킹된 JSON 원본</summary><pre>{h(json.dumps(audit, ensure_ascii=False, indent=2))}</pre></details></section>
</main></body></html>'''
