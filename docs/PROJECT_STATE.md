# Naver SEO Toolkit — 현재 프로젝트 상태

문서 확인: 2026-10-17 KST / 아래 실제 회귀 실행 시각은 2026-10-16 UTC 기록이다. 문서 정정으로 테스트를 재실행하지 않았다. 새 세션은 `AGENTS.md` → 이 문서 → 요청 관련 코드·테스트 순으로 읽는다. 실행 옵션과 상세 사용법은 [README](../README.md)를 참조한다.

## 목적과 현재 범위

WordPress·아임웹·카페24·자체 개발 등 다양한 웹 환경의 고객 의뢰를 접수하고, 공개 기술 환경과 SEO를 읽기 전용으로 분석하는 내부 Python CLI다. 장기 목적에는 캐러셀·이미지 최적화·환경별 적용이 있으나 현재 구현 범위는 **STEP 1~3 및 STEP 3.1**까지다. 조정 세션 1개가 실행 CLI 세션 최대 1개에 순차 위임할 수 있으며, 동시에 수정하는 세션은 1개로 제한한다. 다음 STEP은 사용자 요청 후에만 시작한다.

## 실제 구현 상태와 소스

| 단계 | 확인된 구현 | 실제 소스 / 검증 위치 |
| --- | --- | --- |
| STEP 1 · IMPLEMENTED | 헤더·HTML 기술 단서, CMS/프런트엔드/백엔드/HTTP 서버/CDN, 근거·신뢰도·UNKNOWN, JSON, 오류·SSRF 방어 | `environment_detector/{cli,detect,fetch,safety}.py`; `tests/test_{cli,detect,fetch,safety}.py` |
| STEP 1.1 · IMPLEMENTED | 기존 JSON 종합 HTML, 터미널 요약, 후보/공개 서버/CDN 구분, 이스케이프·마스킹 | `environment_detector/{report,redact}.py`; `tests/test_report.py`; [근거 검토](step1.1-evidence-review.md) |
| STEP 1.2 · 비교 종료 / OPTIONAL | ProjectDiscovery httpx 5개 사이트 비교 실험. 핵심 엔진에는 미통합 | `scripts/step1_2_{collect,report}.py`; `tests/test_step1_2_comparison.py`; [비교와 판정](step1.2-comparison.md) |
| STEP 2 · IMPLEMENTED | 의뢰 정규화·고객별 작업 ID·환경 결과 재사용·동의 확인·사전 수주 판정·고객 질문/내부 작업·HTML | `environment_detector/{intake,projects,pre_review,project_report,project_cli}.py`; `tests/test_projects.py`; `templates/` |
| STEP 3 · IMPLEMENTED | HTTP/robots/Yeti/색인 지시어·메타·제목 계층·링크·ALT·승인된 사이트맵·기존 JSON-LD·중복 메타 검사, SEO JSON/HTML | `environment_detector/seo_{audit,checks,policy,report}.py`; 공통 `fetch.py`; `tests/test_seo.py`, `tests/fixtures/seo/` |
| STEP 3.1 · IMPLEMENTED | 오프라인 통합 Workbench, 단계 탐색·근거 펼치기·기존 보고서 링크·다음 조치·CLI/Codex 텍스트 복사·상태/출처 분리 | `environment_detector/{workbench,workbench_actions,workbench_report}.py`; `project_cli.py`; `tests/test_workbench.py`; `scripts/check_workbench_browser.mjs` |

**현재 대조 결과:** STEP 1~3 및 STEP 3.1 구현은 실제 코드·CLI·회귀와 일치한다. 최초 로컬 기준 커밋 `b560149ecf91`를 생성하고 실제 커밋 export에서 391개 전체 회귀를 통과했다. 원시 분석 JSON 8개는 로컬 보존·Git 제외했으며 순수 합성 fixture 8개를 포함해 추적 파일은 61개다. 제품 기능·JSON·CLI는 유지한다. 검증 기록은 문서 커밋 `40c66b219a3e`에 남겼으며 이번에는 완료 상태와 문서 파일명만 정정했다. 상세 목록·출처·커밋 기록은 [최초 커밋 검토·완료 기록](FIRST_COMMIT_PLAN.md)에 있다. 프로그램 IMPLEMENTED와 실제 고객 작업 COMPLETED는 별개다.

## 데이터와 CLI

- 진입점: `environment_detector/__main__.py` → `cli.py` → `project_cli.py`. Python 요구 버전·의존성은 `pyproject.toml`에 있다(Python ≥3.11, Python httpx, BeautifulSoup, pytest). 이번 검증 환경은 Python 3.14.0이다.
- 프로젝트 기본 위치: `customer-data/projects/JOB-…/`. `intake.json`(intake-1.0), `project.json`(project-1.0), `environment.json`(1.0), `review.json`(pre-review-1.0), `questions.json`(배열), `seo-audit.json`(seo-audit-1.0)을 별도로 보존한다.
- HTML: `report.html`(사전 검토), `seo-report.html`, 선택 생성한 `environment-report.html`, `dashboard.html`. 재검토/재생성 백업은 `history/`. 원본 JSON과 기존 CLI 호환성을 유지한다.

아래 `URL`과 `JOB-ID`는 실제 승인 범위와 작업 ID로 바꾼다. `python` 명령은 프로젝트 루트에서 가상환경을 활성화한 PowerShell 기준이다.

```powershell
# 새 환경 HTTP 분석: 사전에 공개 영역 분석 동의와 URL 확인
python -m environment_detector URL -o results/environment.json --summary
# 저장 JSON → 환경 보고서 (오프라인)
python -m environment_detector report results -o results/report.html
# 의뢰 접수 + 동일 URL의 저장 환경 재사용 (오프라인)
python -m environment_detector project create customer-data/intake/request.json --environment results/environment.json
python -m environment_detector project review customer-data/projects/JOB-ID
# SEO HTTP 분석: 정규 의뢰의 public_analysis_consent가 boolean true여야 함
python -m environment_detector project audit customer-data/projects/JOB-ID
python -m environment_detector project audit customer-data/projects/JOB-ID --report-only
python -m environment_detector project dashboard customer-data/projects/JOB-ID
.\.venv\Scripts\python -m pytest -q
```

`project create --analyze`는 명시적 동의 후 새 환경 분석이다. 소스 옵션 생략 시 캐시만 찾고 자동 HTTP 요청은 하지 않는다. `review`, `--report-only`, `dashboard`는 오프라인이다. `scripts/step3_demo.py`는 고정 모의 HTTP 재현용이며 실제 고객 분석이 아니다. 고객별 자료·개별 작업 진행 상황은 이 문서에 옮기지 않는다.

## 유지할 기술적 결정과 이유

- **외부 엔진 OPTIONAL 유지:** 보조 단서는 유용하지만 현재 필수 탐지·근거 설명을 대체할 필요가 확인되지 않았다. 비교에 고정한 `pd-httpx.exe` v1.12.0은 `tools/projectdiscovery-httpx/`에 별도 보관하며 Python `httpx` 패키지와 구분한다. 새 OSINT 엔진을 추가하지 않는다.
- **공개 증거만 판단:** 자원 경로는 후보이며 서버 내부·원본 서버·자체 개발 여부를 추정하지 않는다. 고객 CMS 진술과 탐지는 서로 덮어쓰지 않는다. READY는 견적 검토 가능이며 실제 수정 권한·배포 승인이 아니다.
- **요청 안전성 재사용:** 공인 DNS 전체 검사·검증 IP 고정·Host/SNI·TLS 검증, 프록시 미사용, 제한된 GET/리다이렉트/본문을 공통 `fetch.py`로 처리한다. SEO 기본 최대 20페이지, 간격 1초, 작업별 타임아웃 10초, 본문 최대 2 MiB다. 내부 탐색·사이트맵은 별도 승인 옵션이며 사이트맵 URL을 무차별 방문하지 않는다.
- **분석/적용 분리:** 초기 HTML에 없는 내용은 렌더링 후에도 없다고 확정하지 않는다. `RENDERING_REQUIRED`/NOT_VERIFIED를 사용하며 실제 색인·순위·캐러셀·성능 측정을 주장하지 않는다.
- **Workbench는 정적 단일 HTML:** 서버·DB·React·외부 CDN 없이 기존 JSON을 투영한다. 복사는 텍스트 기능이고 CLI/Codex를 실행하지 않는다. 권한 미검증 시 Codex 지침은 구현 보류·자료 검토용이다. 고객 자유 문구/페이지 원문은 새 명령으로 해석하지 않는다.
- **세션 복원은 파일 기반:** AGENTS.md에서 이 상태 파일을 읽고 갱신하도록 지시한다. 대화 전체나 프로세스 메모리를 복원하는 기능은 추가하지 않는다. 제품의 기존 기술적 결정은 유지하며, 세션 운영 규칙 변경은 아래에 별도 기록한다.

## 최근 검증·첫 로컬 커밋

- 최초 커밋 작업의 실행 세션: `01a14506-e649-71a3-991c-291340a71885`, 사용자 지시에 따른 YOLO 재개. 추가 Codex 세션/에이전트 없이 같은 단일 작성 세션으로 진행했다. 당시 승인 범위는 명시적 후보 스테이징·첫 로컬 커밋·검증 결과 문서 커밋과 문서 정정이었다. 이후 사용자가 별도로 승인한 원격 push는 아래에 기록한다. 다음 STEP·사이트 요청·브라우저/외부 엔진·설치·전역 설정 변경·기존 이력 재작성은 진행하지 않았다.
- 최신 로컬 전체 회귀: **2026-10-16 14:34:14~14:34:29 UTC**, 기존 `.venv/Scripts/python.exe -m pytest -q` → **391 passed in 13.91s**, 종료 코드 0. 실제 `cwd`는 프로젝트 루트, `environment_detector.__file__`은 그 루트의 `environment_detector/__init__.py`임을 실행 전 assert로 확인했다.
- pytest와 Python 하위 프로세스에서 실네트워크와 원시 fixture 디렉터리 읽기를 차단했다. 커밋 export에서는 원본 프로그램·스크립트·테스트·양식 읽기도 차단해 editable install fallback을 금지했다. 기존 가상환경과 의존성만 재사용했다.
- 보호 대상 39개 중 **36개 SHA-256 동일**: 원시 JSON 8개·프로그램 20개·스크립트 4개·pyproject 1개·가상 예제 JSON 3개. Markdown 양식 3개만 위 줄 끝 공백 수정으로 의도적 해시 변경이며 전후 해시는 `minimal-template-fix.json`에 기록했다. `.gitignore` 불변, 원시 8개 포함 **29개 제외 경로 검사 통과**. 고객 데이터 디렉터리는 읽거나 수정하지 않는다.
- 초기 Git 상태(작업 전 이력): HEAD 커밋 없음·추적/스테이징 파일 0개·인덱스 파일 없음이었다. 현재 커밋 상태는 아래 완료 기록으로 구분한다.
- 로그와 백업은 `results/codex-delegation/commit-20261016T142733Z/`에만 보존한다. `pre-task.zip`·`pre-task-sha256.json`·`initial-git.json`은 이번 작업 전의 제한된 백업/메타데이터이며 고객 자료와 Git author identity를 추적 문서에 기록하지 않는다. 기존 `results/codex-delegation/20261016T140242Z/before.zip`도 보존한다.
- 검토 결과: 기존 후보 **61개**와 명세 일치. 내용 검색 43건은 테스트의 가짜 인증/연락처·공격 입력과 변수명 오탐으로 문맥 검토했고 실제 인증정보/고객 자료·unsafe 추가 파일·필수 파일 누락은 발견하지 않았다. 전용 secret scanner는 설치하지 않았다. 제품·테스트·fixture는 불변이다. 스테이징 검사에서 양식 3개 줄 끝 공백 6곳을 발견해 hardbreak 5곳은 동등한 CommonMark 백슬래시 줄바꿈, 빈 목록 1곳은 공백 제거로 최소 수정했다. 의미·항목은 유지하며 검사 설정을 완화하지 않았다.
- 출처/계약: 기존 **381개 + 출처/독립성 회귀 10개 = 391개**. 백업의 기존 테스트 9개와 assert **507개** 및 decorator/매개변수화 동일. marker 있는 합성 JSON은 실제 관찰로 바꾸지 않고, 구형 출처 미제공 분기는 별도 손 작성한 입력으로 검사한다. UNKNOWN·후보·오류/SSRF·마스킹/XSS·동의·CLI/보고서·OPTIONAL 검증을 유지했다.
- 첫 커밋 완료 작업의 파일 수정: `templates/01_customer_inquiry_quote.md`·`02_customer_technical_handoff.md`·`03_internal_intake_review.md`의 줄 끝 공백, `docs/PROJECT_STATE.md`·`docs/FIRST_COMMIT_PLAN.md`의 승인 범위·Git 사실·검증/커밋 기록. 초기 baseline에는 기존 STEP 1~3.1 코드·양식·설정/문서와 합성 테스트를 함께 포함했다. 이번 최종 정정에서는 위 문서 2개만 변경했다.

## 커밋·완료 상태

- 첫 로컬 기준 커밋: **`b560149ecf910cca224d338b9f7ddc24c9f63c7b`** — `chore: initialize Naver SEO Toolkit (STEP 1-3.1)`. 실제 커밋 시각은 `2026-10-16T14:35:07.855875+00:00`이며 정상 Git hooks/설정으로 생성했다. 별도 identity 설정, force-add, amend/reset, 원격 push는 하지 않았다.
- 커밋 자체 검증: `git archive`로 위 커밋을 `results/codex-delegation/commit-20261016T142733Z/committed-export/`에 새로 내보냈다. export의 파일 61개가 실제 커밋 트리와 일치하고 `.git`·`.venv`·원시 JSON 8개·고객/결과/바이너리는 없다.
- 실제 export import: 기존 가상환경의 Python 절대 경로를 재사용해 cwd를 export로 지정했다. `environment_detector.__file__`이 **`results/codex-delegation/commit-20261016T142733Z/committed-export/environment_detector/__init__.py`**(프로젝트 루트 기준)임을 assert로 확인했다. 원본 소스/원시 fixture 읽기 및 실네트워크를 차단한 상태다.
- export 전체 회귀: **2026-10-16 14:35:13~14:35:28 UTC**, `-m pytest -q` → **391 passed in 14.80s**, 종료 코드 0. 작업 트리 복사본이 아닌 실제 첫 커밋 트리의 결과다.
- 검증 기록은 문서 커밋 **`40c66b219a3e166cdd2993e68bc11c20560125b7`** — `docs: record baseline verification and completion`에 남겼다. 검증한 기준 커밋 이후 변경 파일은 **`docs/PROJECT_STATE.md`와 `docs/FIRST_COMMIT_PLAN.md`**뿐이다. 최종 HEAD의 나머지 **59개 Git blob**은 검증한 기준 커밋과 동일하다. 이번 문서 정정에서는 테스트를 재실행하지 않고 blob 동일성·문서 일관성을 확인했다.
- 최종 추적 파일은 **61개**이며 작업 트리는 깨끗하고 스테이징 항목도 없다. ignored 고객 자료·원시 JSON 8개·results/·도구는 보존했다. 실제 최종 HEAD·부모 이력·상태·검사 결과는 Git 제외 `results/codex-delegation/commit-20261016T142733Z/completion-final.json`에 기록했다. 기존 `completion-summary.json`은 앞선 두 커밋 완료 시점의 이력으로 보존했다.
- 최종 인계 중단은 Git 커밋과 전체 회귀가 성공한 뒤 최종 응답을 전달하는 과정에서 발생한 실행 세션 사용량 한도 오류였다. 같은 ID로 계속해 문서 정정과 최종 인계를 마무리했다. 테스트 실패나 커밋 실패가 아니며 다음 STEP은 시작하지 않았다.
- 이번 요청 범위의 미해결 문제는 없다. STEP 4와 다른 기능 개발은 시작하지 않았다. 합성 회귀 통과는 실제 고객 사이트의 최신 기술·SEO·권한·색인/순위/캐러셀 노출을 입증하지 않는다.

## 현재와 다음 작업

- 현재: 첫 로컬 기준 커밋·실제 커밋 export의 391개 회귀 검증·문서 정정·GitHub push를 완료했다. 저장소는 사용자의 후속 요청에 따라 **공개(PUBLIC)** 상태다. 제품·테스트·입력은 검증한 기준 커밋과 동일하다. 사용자 후속 지시를 기다린다.
- 다음: 사용자 후속 지시 대기. 다음 STEP·사이트 요청·운영 변경은 시작하지 않았다.
- 한계: 실제 고객 권한·운영 환경·검색 노출 검증은 하지 않았다. 합성 입력과 오프라인 회귀는 소프트웨어 동작만 검증한다.

## GitHub 원격 저장소 — 2026-10-17 KST

- 사용자의 명시적 push 요청에 따라 로그인된 `Yanamachi` 계정에 [Naver-SEO-Toolkit](https://github.com/Yanamachi/Naver-SEO-Toolkit)을 처음 비공개로 생성했다. 이후 2026-10-17 KST 사용자의 공개 전환 요청으로 **공개(PUBLIC)**로 변경했다. GitHub의 `isPrivate: false`와 인증 없는 API 조회의 HTTP 200을 확인했다. `origin`은 `https://github.com/Yanamachi/Naver-SEO-Toolkit.git`, 브랜치는 `main`, 추적 대상은 `origin/main`이다.
- 최초 push는 `024a094998698fb0afd1511a2e88e7eeaadcd2eb`까지 반영됐으며 GitHub API의 원격 SHA와 로컬 HEAD 일치를 확인했다. 이번 원격 상태 기록도 같은 브랜치의 문서 커밋으로 관리한다. 최신 동기화는 `git rev-parse HEAD`와 `git ls-remote origin refs/heads/main`으로 확인한다.
- 추적 파일 61개만 업로드한다. 고객 자료·원시 분석 JSON 8개·결과/로그/백업·가상환경·외부 실행 파일·인증정보 제외 정책을 유지한다. 제품·테스트·fixture 변경이 없어 pytest는 다시 실행하지 않았으며 위 391개 회귀 결과와 검증한 Git blob의 동일성을 유지한다.
- 이번 원격 생성·push는 조정 세션이 Git/GitHub CLI로 직접 처리했다. 인증은 기존 GitHub CLI 키링을 재사용했고 push 명령에만 credential helper를 지정했다. 토큰 저장·전역 설정 변경·force push는 하지 않았다. 변경 전 Git 로컬 설정과 상태 문서 백업, 최종 원격 검증 기록은 Git 제외 `results/git-push/`에 있다.
- 공개 전환 전 설정·상태 문서 백업과 인증 없는 조회 검증은 Git 제외 `results/github-visibility/`에 보존했다. 설정 복구가 필요하면 사용자 요청 후 `gh repo edit Yanamachi/Naver-SEO-Toolkit --visibility private --accept-visibility-change-consequences`로 비공개로 되돌릴 수 있다.

## 미구현·제약·미확인

- **NOT_IMPLEMENTED:** Carousel Builder/새 캐러셀 JSON-LD 생성, 이미지 변환·최적화 엔진, 환경별 적용 어댑터·운영 배포, 최종 변경 검증·납품 자동화. 새 SaaS·로그인·결제·DB 서버도 없다.
- 알려진 제약: JS 실행 없음, 앱 셸 판정은 휴리스틱, robots/JSON-LD/사이트맵은 제한된 정적·기본 구조 검사다. 강제 압축 응답을 거절하고 OS DNS 조회는 엄격한 전체 시간 제한을 초과할 수 있다. 세부 제한은 README와 `seo_policy.py`/`seo_checks.py` 참조.
- 환경 파일 자동 교체 CLI는 없다. 새 `environment-candidate.json`은 담당자가 검토·백업·연결해야 한다. HTML은 스냅샷이며 원본 변경 후 명령으로 갱신한다. 마스킹은 알려진 패턴만 다룬다.
- 미확인: 실제 고객의 수정 권한·관리자 접근·운영 승인, 서버 내부 기술, 실제 네이버 색인/순위/캐러셀 노출, 렌더링 후 DOM, Core Web Vitals, 모든 CMS 버전/실제 운영 환경 호환성. 통과한 모의 테스트가 이 사실들을 증명하지 않는다.
- 세션 운영 결정: 조정 세션 1개 + 실행 CLI 세션 최대 1개의 순차 위임을 유지한다. 사용자 지시에 따라 실행 세션 시작·재개는 YOLO 권한으로 운영한다. 실행 경로 접근 문제를 해결하기 위한 권한 변경이며 작업 범위·사이트 접근·스테이징/커밋 규칙을 확대하지 않는다. 병렬 개발·중첩 위임은 허용하지 않는다. 실행 ID·최종 검증 결과는 위 최근 검증에 기록했다.
- Git 제외 정책: `.venv/`, 캐시, `results/`, `customer-data/`, `projects/`, `tools/projectdiscovery-httpx/`와 프로젝트별 `.gitignore`를 유지한다. 원시 분석 결과 복사본 8개와 인증정보·외부 실행 파일 제외를 유지한다. 테스트 재현을 위해 사람이 별도로 구성한 합성 JSON 8개만 후보에 포함한다. 기존 분석 결과 제외 결정은 유지하면서 필수 fixture 누락을 해소하기 위한 출처 정리 결정이며 로컬 원시 파일은 보존했다. 합성 출처를 제거하지 않고 구형 출처 미제공 분기는 별도 손 작성한 테스트 입력으로 유지한다. [출처 설명](../tests/fixtures/synthetic/README.md)에 고정 URL 계약과 역사적 비교 문구의 한계를 기록했다. 추적 문서에는 고객 개인정보·인증정보·고객별 민감 자료를 기록하지 않는다.

## 다음 세션 시작 문구

> AGENTS.md와 docs/PROJECT_STATE.md를 읽고 실제 코드·테스트와 대조해 현재 상태 및 불일치를 짧게 보고하세요. 다음 STEP은 시작하지 말고, 이번에 지정한 작업만 수행하세요. 작업 종료/중단 시 상태 파일을 갱신하고 사용자 승인 없이 커밋하지 마세요.

AGENTS.md의 세션 시작 적용 방식은 [공식 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)를 따른다. PROJECT_STATE.md는 이 저장소의 명시적 읽기 규칙으로 연결한 상태 문서다.
