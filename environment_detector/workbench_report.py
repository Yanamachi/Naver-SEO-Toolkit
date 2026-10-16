"""Single-file, offline project workbench with fixed hash-authorized UI script."""

import base64
import hashlib
import json

from .intake import SERVICES
from .project_report import DECISIONS
from .report import Entry, STYLE, assessment, h, render_entry, result_state
from .seo_report import LABELS as SEO_LABELS, SEVERITIES
from .workbench import STAGES

STATE_LABELS = {"NOT_STARTED": "시작 전", "READY": "검토 준비", "NEED_INFO": "추가 정보 필요", "NEED_REVIEW": "담당자 검토 필요", "COMPLETED": "현재 범위 완료", "BLOCKED": "진행 차단", "NOT_VERIFIED": "미검증"}

SCRIPT = r"""(() => {
  const panels = [...document.querySelectorAll('[data-stage-panel]')];
  const links = [...document.querySelectorAll('[data-stage-link]')];
  function selectStage(id) {
    if (!panels.some(panel => panel.id === id)) id = panels[0].id;
    panels.forEach(panel => { panel.hidden = panel.id !== id; });
    links.forEach(link => {
      const selected = link.getAttribute('href') === '#' + id;
      link.classList.toggle('is-active', selected);
      if (selected) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    });
  }
  links.forEach(link => link.addEventListener('click', () => selectStage(link.hash.slice(1))));
  window.addEventListener('hashchange', () => selectStage(location.hash.slice(1)));
  selectStage(location.hash.slice(1));
  function legacyCopy(value) {
    const input = document.createElement('textarea');
    input.value = value;
    input.setAttribute('readonly', '');
    input.style.position = 'fixed';
    input.style.opacity = '0';
    document.body.appendChild(input);
    input.select();
    try { return document.execCommand('copy'); }
    finally { input.remove(); }
  }
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', async () => {
      const value = document.getElementById(button.dataset.copy).textContent;
      let copied = false;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          try { await navigator.clipboard.writeText(value); copied = true; }
          catch (_) { copied = legacyCopy(value); }
        } else copied = legacyCopy(value);
      } catch (_) { copied = false; }
      document.getElementById('copy-status').textContent = copied
        ? '텍스트를 복사했습니다. 실행은 터미널 또는 Codex CLI에서 직접 진행하세요.'
        : '브라우저에서 복사를 허용하지 않았습니다. 표시된 텍스트를 직접 선택해 복사하세요.';
      button.textContent = copied ? '복사 완료' : '직접 선택해 복사';
    });
  });
})();"""

EXTRA_STYLE = """
:root{background:#f4f6f6;color:#193039;--accent:#087568;--line:#dce5e4;--muted:#60747a}*{box-sizing:border-box}main{max-width:1450px;padding:28px 32px 70px}h1{font-size:2rem;letter-spacing:-.04em}h2{font-size:1.3rem}h3{font-size:1.02rem}header.hero{background:#153e42;color:white;border-radius:16px;padding:28px 32px;margin-bottom:22px}header .eyebrow{color:#9fe4d6}header .muted{color:#c0d8d9}.hero-line{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}.hero-url{color:#d6e9e8;overflow-wrap:anywhere}.pill{max-width:100%;overflow-wrap:anywhere;display:inline-flex;align-items:center;padding:3px 10px;border-radius:20px;font-size:.77rem;font-weight:650;white-space:normal;background:#edf2f2;color:#506367}.pill.COMPLETED{background:#d8eee5;color:#15533f}.pill.READY{background:#dff1ee;color:#006c5f}.pill.NEED_INFO,.pill.NEED_REVIEW{background:#fff0d4;color:#805812}.pill.BLOCKED{background:#fbe1e2;color:#922b35}.pill.NOT_VERIFIED{background:#ece6f6;color:#624580}.impl{font-size:.7rem;color:#43636a;letter-spacing:.02em}.future .impl{color:#7b6c58}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}.metric{padding:18px 20px;background:white;border:1px solid var(--line);border-radius:12px}.metric strong{display:block;font-size:1.5rem;letter-spacing:-.03em}.metric span{font-size:.83rem;color:var(--muted)}.workspace{display:grid;grid-template-columns:255px minmax(0,1fr);gap:26px;align-items:start}.sidebar{position:sticky;top:18px;background:white;border:1px solid var(--line);border-radius:12px;padding:16px}.sidebar nav{display:block}.stage-link{display:block;text-decoration:none;border-radius:8px;padding:12px 10px;margin:4px 0;border:1px solid transparent;color:#324d54}.stage-link.is-active{background:#edf8f5;border-color:#b4d8ce}.stage-link strong{font-size:.9rem;display:block}.stage-link .impl{display:block;margin:3px 0 6px}.stage-number{color:#809292;margin-right:8px;font-size:.76rem}.panel{min-width:0}.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}.card{margin:0 0 20px;padding:24px;border-color:var(--line)}.notice{margin:0 0 20px;border-left-color:var(--accent);background:#e6f2ef;border-radius:0 8px 8px 0}.synthetic-warning{background:#fff2d8;border-left-color:#b97c14}.subtle{color:var(--muted);font-size:.85rem}.report-links{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:22px}.report-link{padding:8px 12px;border:1px solid var(--line);background:white;border-radius:8px;font-size:.85rem;text-decoration:none}.unavailable{color:#7a8789;background:#edf1f1}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}.question-list{padding-left:20px}.question-list li{margin-bottom:10px}.action{border:1px solid var(--line);border-radius:10px;padding:18px;margin:14px 0;background:#fcfdfd}.action-head{display:flex;justify-content:space-between;align-items:start;gap:12px}.action h4{margin:0;font-size:1rem}.action-type{font-size:.73rem;letter-spacing:.06em;color:var(--accent);font-weight:700;margin:0 0 5px}.human{background:#f8fafb}.command{position:relative}.command pre{font-family:Consolas,monospace;font-size:.81rem;user-select:text;border-radius:8px;max-height:370px;overflow:auto}.copy-button{cursor:pointer;border:1px solid #a9c9c3;border-radius:7px;padding:7px 12px;background:#e8f5f0;color:#14584e;font-weight:650;white-space:nowrap}.copy-button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #ce971f;outline-offset:3px}summary{padding:8px 0}details.card>summary{color:#334f55}dl{grid-template-columns:150px minmax(0,1fr);font-size:.92rem}.findings .finding{border-top:1px solid var(--line);padding:12px 0}.finding h4{margin:8px 0}.finding pre{max-height:420px;overflow:auto}.criteria{border:1px dashed #b7ccc6;padding:14px 16px;border-radius:8px;background:#f7fbf9}.criteria strong{font-size:.85rem}.source-table{font-size:.82rem}#copy-status{position:sticky;bottom:10px;z-index:5;background:#153e42;color:white;border-radius:9px;padding:0 16px;max-width:850px;margin:12px auto 0}#copy-status:not(:empty){padding:12px 16px}.future-note{font-size:.95rem;color:#655a4c}p,li,dd,pre{overflow-wrap:anywhere}.source-note{font-size:.8rem;color:#667e83}footer{margin-top:30px;font-size:.82rem;color:var(--muted)}@media(max-width:900px){.workspace{grid-template-columns:1fr}.sidebar{position:static}.sidebar nav{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.stage-link{margin:0}.two-col{grid-template-columns:1fr}}@media(max-width:600px){main{padding:16px 12px 40px}.hero-line{display:block}header.hero{padding:22px 20px}h1{font-size:1.65rem}.metric{padding:14px}.metric strong{font-size:1.25rem}.card{padding:18px}.action{padding:14px}.action-head{flex-wrap:wrap}.sidebar{padding:10px}.stage-link{padding:10px 8px}.stage-link strong{font-size:.83rem}.pill{font-size:.69rem}.stage-number{margin-right:5px}dl{grid-template-columns:1fr}.report-link{font-size:.8rem}}@media print{.workspace{display:block}.sidebar,.copy-button,#copy-status{display:none}.panel[hidden]{display:block!important}.hero{color:#193039!important;background:white!important}.card{break-inside:auto}.metrics{display:flex}.panel{margin-bottom:40px}}
"""


def items(values):
    values = list(values)
    return '<ul class="question-list">' + "".join(f"<li>{h(v)}</li>" for v in values) + "</ul>" if values else '<p class="subtle">현재 저장된 항목 없음</p>'


def json_detail(label, data):
    return f'<details><summary>{h(label)}</summary><pre>{h(json.dumps(data, ensure_ascii=False, indent=2))}</pre></details>'


def render_dashboard(model):
    artifacts = model["artifacts"]
    request = artifacts["intake"]["data"]["request"]
    env, review, seo = (artifacts[k]["data"] for k in ("environment", "review", "seo"))
    states = model["states"]
    completed = sum(state[0] == "COMPLETED" for state in states.values())
    implemented_count = sum(stage[3] for stage in STAGES)
    sample = '<aside class="notice synthetic-warning"><strong>가상 테스트 데이터 포함 · 실제 고객 검증 완료가 아닙니다</strong><p>단계별 출처를 확인하세요. 가상 기술 신뢰도와 모의 분석은 실제 운영 환경의 확인 근거로 사용하지 않습니다.</p></aside>' if model["synthetic"] else ""
    nav = "".join(f'<a class="stage-link {"future" if not implemented else ""}" href="#stage-{key}" data-stage-link><strong><span class="stage-number">{number}</span>{h(title)}</strong><span class="impl">{"IMPLEMENTED · 프로그램 구현됨" if implemented else "NOT_IMPLEMENTED · 개발 예정"}</span><span class="pill {states[key][0]}">{states[key][0]} · {STATE_LABELS[states[key][0]]}</span></a>' for key, number, title, implemented, _ in STAGES)
    report_links = "".join(f'<a class="report-link" href="./{r["filename"]}" target="_blank" rel="noopener noreferrer">{h(r["label"])} 열기 ↗</a>' if r["available"] else f'<span class="report-link unavailable">{h(r["label"])} · 미생성/경로 확인</span>' for r in model["reports"])
    bodies = {}
    fields = (("업체명", request.get("company_name")), ("업종", request.get("industry")), ("홈페이지", request.get("site_url")),
              ("요청 서비스", ", ".join(SERVICES.get(s, s) for s in request.get("requested_services", []))),
              ("대상 페이지", " / ".join(request.get("target_page_urls", []))), ("고객이 알고 있는 환경", request.get("reported_cms")),
              ("공개 분석 동의", "동의" if request.get("public_analysis_consent") is True else "미동의/미확인"),
              ("수정 담당자 (고객 진술)", request.get("modification_owner")), ("수정 경로 (고객 진술)", request.get("modification_route")))
    bodies["intake"] = '<section class="card"><h3>접수한 고객 정보</h3><dl>' + "".join(f"<dt>{h(label)}</dt><dd>{h(value or '미확인')}</dd>" for label, value in fields) + '</dl><p class="subtle">CMS 진술·담당자·수정 경로는 고객 입력이며 실제 기술·권한 검증과 다릅니다.</p>' + json_detail("입력 검증 항목", artifacts["intake"]["data"].get("validation_issues", [])) + '</section>'
    if env:
        env_html = render_entry(Entry("저장된 환경 분석의 전체 근거", env, result_state(env)), 1, synthetic=model["env_synthetic"] or model["synthetic_project"])
        tech = []
        for key, label in (("cms", "CMS"), ("frontend", "프런트엔드"), ("backend", "백엔드"), ("server", "HTTP 응답 서버"), ("cdn", "CDN")):
            value = " / ".join(i["name"] + " · " + ("가상 예시" if model["env_synthetic"] else assessment(key, i)[0]) for i in env["technologies"][key])
            tech.append(f"<dt>{label}</dt><dd>{h(value)}</dd>")
        bodies["environment"] = f'<section class="card"><h3>기술 환경 요약</h3><dl>{"".join(tech)}</dl><p class="source-note">원본 시점: {h(env.get("analyzed_at", "UNKNOWN"))} · 최신성: {h(model["env_age"]["freshness"])} · 경과 일수: {h(model["env_age"].get("age_days"))}</p><p class="subtle">공개 HTTP 서버 표기는 프록시·CDN일 수 있습니다. 원본 서버·자체 개발 여부는 UNKNOWN입니다.</p><details><summary>기술 담당자용 상세 근거 펼치기</summary>{env_html}</details></section>'
    else:
        bodies["environment"] = '<section class="card"><p>사용할 수 있는 환경 결과가 없습니다. ' + h(artifacts["environment"]["note"]) + '</p></section>'
    comparison = model["comparison"]
    comparison_labels = {"UNVERIFIED": "대조 근거 부족", "CONSISTENT_CLUES": "진술과 공개 단서가 부합 · 확정 아님", "DIFFERENT_CLUES": "진술과 공개 단서가 다름 · 담당자 확인 필요"}
    customer = [q["question"] for q in model["questions"] if q["audience"] == "customer"]
    internal = [q["question"] for q in model["questions"] if q["audience"] == "internal"]
    decision_html = f'<p><strong>{h(review["decision"])} · {h(DECISIONS[review["decision"]])}</strong> (원본에 저장된 판정)</p>{items(review["reasons"])}<p class="source-note">검토 시각: {h(review.get("reviewed_at", "미확인"))}</p>' if review else '<p>사전 수주 판정 미생성 또는 형식 확인 필요</p>'
    bodies["review"] = f'<section class="card"><h3>수주 가능성 및 판정 근거</h3>{decision_html}<p class="subtle">READY는 견적 검토 가능이라는 뜻입니다. 운영 작업·배포 승인이나 고객 작업 전체 완료가 아닙니다.</p><h3>고객 진술과 현재 기술 단서 대조</h3><p>고객 진술: {h(comparison["customer_reported"])}<br>공개 CMS 단서: {h(" / ".join(comparison["observed_cms"]) or "UNKNOWN")}<br>{h(comparison_labels[comparison["state"]])}</p>{json_detail("원본 사전 검토에 저장된 대조 내용", (review or {}).get("environment_comparison", {}))}</section><section class="card"><div class="two-col"><div><h3>고객에게 확인 ({len(customer)}개)</h3>{items(customer)}</div><div><h3>내부 검토 작업 ({len(internal)}개)</h3>{items(internal)}</div></div><p class="subtle">스크린샷 자료명은 실파일 확보 증거가 아닙니다. 질문 JSON 두 개가 다르면 양쪽을 보존해 표시합니다.</p></section>'
    if seo:
        summary = seo["summary"]
        priority_rows = "".join(f'<tr><td>{h(SEVERITIES[f["severity"]])}</td><td>{h(f["title"])}<br><small>{h(f["url"])}</small></td><td>{h(f["recommendation"])}</td></tr>' for f in model["priorities"][:100])
        findings = []
        for f in seo["findings"][:500]:
            findings.append(f'<details class="finding"><summary>{h(SEO_LABELS[f["result"]])} · {h(f["title"])}</summary><p class="source-note">{h(f["id"])} · {h(f["url"])}</p><p><strong>이유:</strong> {h(f["reason"])}</p><p><strong>개선 권고:</strong> {h(f["recommendation"])}</p><pre>{h(json.dumps(f["evidence"], ensure_ascii=False, indent=2))}</pre><p class="source-note">공식 근거 문서 (텍스트): {h(" / ".join(str(v) for v in f["documentation"]))}</p></details>')
        bodies["seo"] = f'<section class="card"><h3>저장된 SEO 진단 결과</h3><p>분석한 HTML {summary["analyzed_pages"]}페이지 · 실패/차단/비HTML {summary["failed_pages"]}페이지 · 저장 상태 {h(seo["status"])}</p><p class="source-note">분석 시각: {h(seo.get("analyzed_at", "미확인"))} · 출처: {h(seo.get("data_origin", "미확인"))}</p><p>{h(" · ".join(SEO_LABELS[key] + " " + str(model["seo_counts"].get(key, 0)) + "건" for key in SEO_LABELS))}</p><h3>우선순위별 다음 검토</h3><div class="scroll"><table><thead><tr><th>중요도</th><th>문제와 대상</th><th>권장 조치</th></tr></thead><tbody>{priority_rows}</tbody></table></div><p class="subtle">문제가 발견되었다는 사실과 수정 완료는 다릅니다. 초기 HTML 검사만으로 실제 색인·순위·성능을 확인하지 않습니다.</p><details class="findings"><summary>전체 진단 근거 펼치기 ({len(seo["findings"])}건)</summary>{"".join(findings)}</details>{"<p>500건을 넘는 상세는 기존 SEO 보고서와 JSON에서 확인하세요.</p>" if len(seo["findings"]) > 500 else ""}</section>'
    else:
        bodies["seo"] = f'<section class="card"><p>저장된 SEO 진단 결과가 없습니다. {h(artifacts["seo"]["note"])}</p><p>분석한 페이지 수나 진단 결과를 임의로 생성하지 않습니다.</p></section>'
    for key, _, _, _, _ in STAGES[4:]:
        bodies[key] = '<section class="card"><p class="future-note">NOT_IMPLEMENTED · 개발 예정</p><p>현재 실행 엔진·CLI·고객 작업 산출물이 없습니다. 이 단계의 프로그램 구현 여부와 고객별 작업 결과를 별도로 연결할 수 있도록 단계 정보를 분리했습니다.</p><p>현재 화면에서는 준비 자료와 사람이 확인할 작업만 안내합니다.</p></section>'
    action_index = 0
    def render_actions(key):
        nonlocal action_index
        cards = []
        for action in model["actions"]:
            if action["stage"] != key:
                continue
            action_index += 1
            kind = action["kind"]
            label = {"CLI": "A · 기존 CLI", "CODEX": "B · CODEX 자료 검토 / 구현 보류", "HUMAN": "C · 사람이 직접 확인"}[kind]
            if kind == "HUMAN":
                body = f'<dl><dt>담당</dt><dd>{h(action["owner"])}</dd><dt>필요한 정보</dt><dd>{h(action["information"])}</dd><dt>완료 조건</dt><dd>{h(action["complete"])}</dd></dl>'
                button = ""
            else:
                copy_id = f"copy-{action_index}"
                body = f'<p>{h(action["description"])}</p><dl><dt>사전 조건</dt><dd>{h(action["conditions"])}</dd><dt>예상 산출물</dt><dd>{h(action["output"])}</dd></dl><div class="command"><pre id="{copy_id}">{h(action["text"])}</pre></div>'
                button = f'<button type="button" class="copy-button" data-copy="{copy_id}" aria-label="{h(action["title"])} 텍스트 복사" hidden>{"명령어 복사" if kind == "CLI" else "Codex 검토 지침 복사"}</button>'
            cards.append(f'<article class="action {"human" if kind == "HUMAN" else ""}"><p class="action-type">{label}</p><div class="action-head"><h4>{h(action["title"])}</h4>{button}</div>{body}</article>')
        return '<section class="card"><h3>다음에 수행할 작업</h3><p class="subtle">복사 버튼은 텍스트만 복사합니다. PowerShell 또는 Codex CLI의 대화 입력에서 내용을 검토한 뒤 직접 사용하세요.</p>' + ("".join(cards) or '<p>현재 의뢰 범위에서 실행하거나 고객에게 요청할 작업이 없습니다.</p>') + '</section>'
    panels = []
    for key, number, title, implemented, criteria in STAGES:
        state, reason = states[key]
        panels.append(f'<section class="panel" id="stage-{key}" data-stage-panel aria-label="{h(title)}"><section class="card"><p class="eyebrow">WORKFLOW {number}</p><div class="panel-heading"><h2>{h(title)}</h2><span class="pill {state}">{state} · {STATE_LABELS[state]}</span></div><p class="impl">{"IMPLEMENTED · 프로그램 구현됨" if implemented else "NOT_IMPLEMENTED · 개발 예정"}</p><p>{h(reason)}</p><div class="criteria"><strong>현재 단계의 완료 기준</strong><p>{h(criteria)}</p></div></section>{bodies[key]}{render_actions(key)}</section>')
    source_rows = "".join(f'<tr><td>{h(a["filename"])}</td><td>{h({"AVAILABLE": "읽음", "MISSING": "미생성", "INVALID": "형식/경로 확인 필요"}[a["state"]])}</td><td>{h(a["note"])}</td></tr>' for a in artifacts.values())
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode("utf-8")).digest()).decode("ascii")
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"><title>고객 프로젝트 통합 작업 화면</title><style>{STYLE}{EXTRA_STYLE}</style></head><body><main>
<header class="hero"><div class="hero-line"><div><div class="eyebrow">NAVER SEO TOOLKIT · PROJECT WORKBENCH</div><h1>{h(request.get('company_name') or '업체명 확인 필요')}</h1><p class="hero-url">{h(request.get('site_url') or 'URL 미확인')}</p></div><div><p>{h(model['job_id'])}</p><p class="muted">{'저장된 작업 ID' if model['id_from_metadata'] else '폴더 식별자 · 프로젝트 메타데이터 없음'}</p></div></div><p class="muted">요청 서비스: {h(', '.join(SERVICES.get(s, s) for s in request.get('requested_services', [])) or '미기재')}</p></header>
{sample}<div class="metrics"><div class="metric"><strong>{completed} / {len(STAGES)}</strong><span>고객 단계의 현재 범위 완료</span></div><div class="metric"><strong>{implemented_count} / {len(STAGES)}</strong><span>프로그램 구현 단계 · 고객 완료와 별도</span></div><div class="metric"><strong>{len(customer)} / {len(internal)}</strong><span>고객 질문 / 내부 검토 항목</span></div><div class="metric"><strong>{len(model['priorities']) if seo else '미진단'}</strong><span>SEO 개선·검토 항목</span></div></div>
<div class="report-links" aria-label="기존 단계별 보고서">{report_links}</div>
<p class="source-note">개별 HTML은 생성 당시의 스냅샷입니다. 원본 JSON을 변경했다면 해당 CLI로 개별 보고서도 다시 생성하세요.</p>
{'<aside class="notice"><strong>자료 확인 필요</strong>' + items(model['notices']) + '</aside>' if model['notices'] else ''}
<noscript><p class="notice">JavaScript가 꺼져 있어 모든 단계를 표시합니다. 텍스트는 직접 선택해 복사하세요.</p></noscript>
<div class="workspace"><aside class="sidebar"><p class="eyebrow">전체 업무 단계</p><nav aria-label="프로젝트 업무 단계">{nav}</nav><details><summary>상태 읽는 방법</summary><p class="subtle">IMPLEMENTED는 프로그램 기능의 존재입니다. 아래 상태는 고객 자료와 저장된 결과에서 별도로 계산합니다.</p>{items(k + ': ' + v for k, v in STATE_LABELS.items())}<p class="subtle">COMPLETED도 해당 단계의 현재 범위만 의미합니다. 전체 작업·수정·운영 배포 완료와 다릅니다.</p></details></aside><div style="min-width:0">{''.join(panels)}</div></div>
<details class="card"><summary>읽은 원본 파일과 생성 시점</summary><p>화면 생성: {h(model['generated_at'])}</p><p>고객 원본과 기존 JSON은 변경하지 않습니다. 변경 사항은 dashboard 명령을 다시 실행해 반영하세요.</p><div class="scroll"><table class="source-table"><thead><tr><th>파일</th><th>상태</th><th>확인 내용</th></tr></thead><tbody>{source_rows}</tbody></table></div></details>
<div id="copy-status" role="status" aria-live="polite"></div><footer>읽기 전용 오프라인 작업 화면 · 자동 실행·실시간 갱신 없음 · 실제 네이버 색인·순위·캐러셀 노출·운영 수정 권한은 미검증입니다.</footer>
</main><script>{SCRIPT}</script></body></html>'''
