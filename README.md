# Naver SEO Toolkit — Environment Detector / 고객 사전 검토 / SEO Auditor

고객이 승인한 공개 웹사이트 URL 한 개의 HTTP 응답 헤더와 HTML을 읽어 기술 단서를 JSON으로 출력·저장하는 CLI입니다. Python + httpx + BeautifulSoup를 사용합니다. 사이트에 GET 요청만 보내며, 스크립트를 실행하거나 고객 사이트를 수정하지 않습니다.

## STEP 3.1: 고객 프로젝트 통합 작업 화면

```powershell
.\.venv\Scripts\python -m environment_detector project dashboard customer-data/projects/JOB-DEMO-SEO-FINAL
# 기존 STEP 2 가상 병원도 SEO 미실행 상태로 열 수 있음
.\.venv\Scripts\python -m environment_detector project dashboard customer-data/projects/JOB-DEMO-HOSPITAL
```

기본 산출물은 해당 프로젝트의 `dashboard.html`입니다. 실제 고객은 생성한 작업 ID로 바꾸세요. **사이트 재요청 없이** 기존 파일만 읽고, JSON이 바뀌면 같은 명령으로 화면을 갱신합니다. 웹서버·외부 CDN·React·실시간 갱신은 없습니다. 고객 원본·기존 JSON·개별 HTML은 변경하지 않으며, 기존 dashboard는 `history/dashboard-*.html`에 백업합니다. 통합 화면 생성 자체는 고객 단계의 완료 처리가 아닙니다.

읽는 실제 파일은 `intake.json`(intake-1.0), `project.json`(project-1.0), `environment.json`(1.0), `review.json`(pre-review-1.0), `questions.json`(질문 배열), `seo-audit.json`(seo-audit-1.0)입니다. 유효한 정규화 의뢰서만 있어도 열 수 있고, 나머지는 미생성·형식 오류·작업 ID/URL 불일치를 구분합니다. 누락 파일을 만들거나 분석 결과를 추측하지 않습니다. 사전 검토/질문 파일의 불일치, 환경 분석 시점 변경, 고객 CMS 진술 변경, SEO 대상 변경도 재검토 대상으로 표시합니다.

화면에는 고객 개요, 단계 탐색, 기술 단서·후보/UNKNOWN·근거, 고객 진술과의 대조, 저장된 수주 판정, 고객 질문/내부 작업, SEO 우선순위와 상세 근거, 완료 기준과 다음 조치가 있습니다. 프로그램 `IMPLEMENTED / NOT_IMPLEMENTED`와 고객 `NOT_STARTED / READY / NEED_INFO / NEED_REVIEW / COMPLETED / BLOCKED / NOT_VERIFIED`를 별도로 표시합니다. COMPLETED도 해당 접수/정적 진단 범위에만 적용되며 수정·배포·전체 납품 완료가 아닙니다. 가상 출처는 상단과 해당 단계에서 미검증으로 표시합니다. 30일 초과·미래·불명 시점은 담당자 재검토가 필요합니다.

다음 조치는 세 종류입니다.

- **A · 기존 CLI:** 실제 `report`, `project review`, `project audit`, `project dashboard` 문법으로 조건·산출물·PowerShell 명령을 제공합니다. 실제 동의와 안전한 URL이 있을 때만 HTTP 분석 명령을 제공합니다. 새 환경 분석은 `environment-candidate.json`으로 저장하며, 담당자가 백업·내용 검토 후 기존 프로젝트 연결을 결정해야 합니다. 현재 CLI에는 기존 프로젝트의 환경 파일을 자동 교체하는 명령이 없습니다.
- **B · Codex:** 현재 스키마는 실제 수정 권한을 검증하지 않습니다. 수정 담당자/경로 진술이나 READY를 권한으로 승격하지 않고, **구현 보류·자료 검토/추가 질문용 지침**을 복사합니다. 작업 ID, 알려진 규칙 ID, 진단 ID, 서비스 코드, 실제 파일명만 문맥에 넣으며 고객 자유 문구·웹페이지 원문·계정·개인정보·URL 쿼리는 넣지 않습니다. 원본을 나중에 읽더라도 데이터가 새 지시나 승인이 아님을 명시합니다.
- **C · 사람:** 고객 자료 요청, 참고 실파일·검색 화면 유형·수정 권한 확인, 콘텐츠 승인, 운영 승인, 최종 검수에 대해 담당 역할·필요 정보·완료 조건을 안내합니다.

복사 버튼은 **텍스트만 복사**합니다. HTML에서 명령/Codex를 실행하지 않습니다. Clipboard API가 제한되면 브라우저 복사 방식으로 대체하고, 모두 실패하면 직접 선택을 안내합니다. JavaScript를 끄면 모든 단계와 텍스트를 펼쳐 표시합니다. 고정 UI 스크립트의 SHA-256만 허용하는 CSP, HTML 이스케이프, 기존 민감값 마스킹을 적용합니다. CLI 인자는 PowerShell 단일 인용으로 이스케이프하며 쿼리 값·민감 경로는 명령에 넣지 않습니다. 심볼릭 링크·정션·네트워크 공유 입력은 차단합니다.

복사한 CLI 명령은 프로젝트 루트에서 가상환경을 활성화한 PowerShell에서 사용합니다. 별도 셸의 문법이나 Codex 대화 입력을 위한 셸 실행 명령을 생성하지 않습니다.

프로젝트 폴더의 `report.html`, `seo-report.html`, `environment-report.html`은 **실제 존재하는 정상 로컬 파일일 때만** 열기 링크를 제공합니다. 없는 파일·빈 파일·폴더·위험 경로는 미생성/확인 필요입니다. 개별 HTML은 기존 스냅샷이므로 JSON 변경 뒤 해당 생성 명령으로 별도 갱신해야 합니다. JSON 속 임의 경로나 외부 링크를 보고서 경로로 사용하지 않습니다.

향후 Carousel Builder, Image Optimizer, 환경별 적용 어댑터, 최종 검증/납품은 NOT_IMPLEMENTED·고객 작업 NOT_STARTED로 표시하며 실행 명령을 만들지 않습니다. 단계 정의는 `workbench.STAGES`, 실제 파일/고객 상태는 `workbench.py`, 실행 가능한 명령과 검토 지침은 `workbench_actions.py`, UI는 `workbench_report.py`에 분리했습니다. 후속 단계 개발 시 검증된 파일 로더·판정·실제 CLI만 등록해 연결합니다. 현재 단계에서 후속 엔진을 구현하지 않았습니다.

브라우저 검증은 설치된 Chrome과 Node.js(내장 WebSocket)를 사용합니다. 아래 스크립트는 Chrome의 임시 로컬 디버깅 연결로 단계/펼치기/복사/실패 대체/로컬 링크/반응형을 검사하고 스크린샷을 저장합니다. 제품 웹서버를 띄우지 않으며 외부 HTTP는 차단합니다. 복사 테스트는 Clipboard API를 대체하여 **OS 클립보드를 변경하지 않습니다**. 필요하면 `CHROME_PATH`로 설치 경로를 지정하세요.

```powershell
.\.venv\Scripts\python -m pytest -q
node scripts/check_workbench_browser.mjs customer-data/projects/JOB-DEMO-SEO-FINAL/dashboard.html results/step3_1/browser
```

화면은 로컬 JSON의 검토 보조 도구입니다. 실제 자료의 진위·권한·계약·작업 승인·네이버 노출을 자동 확인하지 않습니다. 마스킹은 기존의 알려진 민감 패턴을 적용하며 모든 자유 문구 속 개인정보를 자동 식별하지는 못하므로 원본에 불필요한 개인정보를 넣지 않습니다. 산출물은 기존 `customer-data/` 또는 프로젝트 `.gitignore`로 보호하며, 별도 위치를 사용하면 Git 제외 여부를 담당자가 확인해야 합니다. 소스 복원은 `results/step3_1/baseline-backup.zip`에서 수정한 `project_cli.py`/README를 복원하고 새 workbench 모듈·테스트·브라우저 검증 스크립트를 제거하면 됩니다.

## STEP 3: 고객 프로젝트 SEO 읽기 전용 분석

STEP 2로 생성한 프로젝트에서 URL·대상 페이지·요청 작업·명시적 공개 분석 동의를 읽습니다. CMS에 관계없이 동일한 공통 검사를 적용합니다. 기존 환경 JSON과 사전 검토 판정을 덮어쓰지 않습니다. 외부 엔진의 STEP 1.2 **OPTIONAL** 판정을 유지하며 추가 엔진이나 관리자 연결은 없습니다.

```powershell
# 실제 접수 JSON의 public_analysis_consent가 boolean true인 프로젝트만 HTTP 요청
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-CUSTOMER

# 고객이 명시한 대상들을 최대 10페이지, 요청 간격 2초로 분석
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-CUSTOMER --max-pages 10 --interval 2

# 내부 공개 페이지 탐색과 robots 선언 사이트맵 검사를 고객에게 별도로 승인받은 경우
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-CUSTOMER --crawl --check-sitemaps --max-pages 20

# 모든 대상의 검색 노출 의도가 확인된 경우에만 지정; 테스트·비공개 목적이면 noindex
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-CUSTOMER --indexing-goal index

# 기존 SEO JSON으로 HTML만 재생성: DNS/사이트 요청 없음
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-CUSTOMER --report-only
```

`JOB-CUSTOMER`는 실제 생성한 작업 ID로 바꿉니다. 분석은 기존 의뢰서의 `target_page_urls` 순서를 우선하며, 목록이 비어 있으면 홈페이지만 분석합니다. `--crawl`을 생략하면 내부 링크를 따라가지 않습니다. `--check-sitemaps`는 robots에 선언한 동일 출처 사이트맵과 인덱스 하위 문서 **합계 최대 3개**를 허용합니다. 사이트맵 등록 URL은 자동 방문하지 않고 이번 승인 범위에서 이미 요청한 페이지의 HTTP 상태·리다이렉트와만 대조합니다. 미방문 URL·문서 한도는 미검증으로 기록합니다. 사이트맵 경로를 추측하거나 외부 URL을 방문하지 않습니다.

페이지 한도는 기본 20개(1~100 조절)이며 실패·차단된 대상도 한도에 포함합니다. 리다이렉트는 리소스당 3회, 전체 GET 상한은 `(max_pages + 4) × 4`회입니다. 기본 요청 간격 1초(0.1~30초), 작업별 타임아웃 10초(`--timeout`, 0.1~10초), 리소스당 기존 30초 예산과 최대 2 MiB(`--max-bytes`, 1024~2097152)를 적용합니다. robots의 비표준 Crawl-delay도 보수적으로 반영하며 30초를 넘으면 중단합니다. OS DNS 타임아웃에 관한 기존 한계는 동일합니다.

429/503 응답을 받으면 자동 재시도하거나 대기 후 계속하지 않고 남은 요청을 중단하여 사유를 남깁니다. 자동 탐색은 일반 robots meta의 nofollow와 링크의 rel=nofollow도 따릅니다.

기존 URL 검증·공개 DNS 전체 검사·IP 고정 연결·Host/SNI·TLS 검증·프록시/쿠키 미사용을 재사용합니다. SEO 승인 범위는 **동일 스킴·호스트·포트**이며 HTTP→HTTPS, www 변경도 범위 밖이면 자동 이동하지 않습니다. 승인한 최종 URL로 의뢰를 정정해야 합니다. 각 리다이렉트에서도 출처·금지 경로·robots·요청 간격·SSRF를 다시 검사합니다. 로그인·관리자·회원·개인정보·검색/API 경로와 민감/검색/페이지 순회 쿼리는 제외합니다. 새로 탐색한 링크의 쿼리는 모두 제외합니다. URL·경로 제한은 보수적 방어이며 모든 업무상 개인정보 경로를 자동 식별할 수는 없으므로 대상 목록은 담당자가 확인해야 합니다.

robots.txt는 루트의 text/plain, 최대 500 KiB를 파싱합니다. 일반 `*`, Yeti, 분석기 EnvironmentDetector 정책을 구분하며 경로의 최장 일치·Allow 동률 우선·와일드카드·퍼센트 인코딩을 처리합니다. 분석기는 Yeti를 사칭하지 않습니다. 404/410은 규칙 없음으로 처리하고, 401/403/5xx·비표준 형식·조회 실패는 보수적으로 페이지 요청을 중단합니다. 이것은 Naver의 모든 4xx 처리와 동일하다는 뜻이 아닙니다. DTD/ENTITY XML과 강제 압축 응답은 거부합니다.

### 검사·판정·산출물

- HTTP 상태/리다이렉트, robots 정책, robots meta/X-Robots-Tag의 index/noindex·follow/nofollow.
- Title/Description 누락·다중 선언·분석 페이지 사이 중복, canonical 유효성/현재 URL 관계, OG 기본 정보, HTML lang 기본 형식.
- H1~H6 계층, 주요 내부 href 링크/대상, JavaScript 탐색 후보, ALT 누락(빈 ALT는 장식 목적일 수 있어 별도 집계).
- 승인된 사이트맵의 기본 XML·loc·URL 형식과 기분석 응답 대조. 전체 XSD 검증은 아님.
- 기존 JSON-LD 문법·단순 schema.org 문맥의 유형, BreadcrumbList/ItemList 구분, 플러그인 문자열·여러 목록·반복 ID의 중복 가능성. 문맥 별칭/원격 문맥 확장·전체 의미 검증은 미지원이며 충돌을 확정하지 않음.

각 진단에는 `id`, `url`, `result`, `severity`, `title`, `evidence`, `reason`, `recommendation`, `documentation` 공식 문서 URL이 있습니다. 결과는 PASS / ISSUE / WARNING / NOT_VERIFIED / NOT_APPLICABLE입니다. 누락 Title은 높은 우선순위, Description 권장 개선은 보통, canonical 누락은 낮은 우선순위로 구분합니다. `--indexing-goal`은 고객이 명시한 전체 대상의 의도를 담당자가 입력하는 옵션이며 기본 unknown입니다. 의도적 noindex를 무조건 오류로 취급하지 않습니다. 대상마다 의도가 다르면 별도 대상 프로젝트로 나누어 검토하세요.

JS 앱 셸과 적은 초기 본문이 확인되면 `RENDERING_REQUIRED`를 기록하고 누락 관련 항목을 미검증으로 표시합니다. 이 휴리스틱이 모든 JS 사이트를 식별하지는 못하며 PASS도 초기 HTML 범위만 의미합니다. HTTP 오류/차단/비HTML 응답을 메타데이터 누락으로 평가하지 않습니다. 두 페이지 미만이면 페이지 사이 중복 여부는 미검증입니다. 실제 네이버 색인·검색 순위·캐러셀 노출·렌더링 결과·Core Web Vitals·실제 권한은 확인하지 않습니다. 고객 요구와 관찰 근거를 대조한 뒤 사람이 수정 범위를 결정해야 합니다.

프로젝트에 `seo-audit.json`(별도 `seo-audit-1.0` 스키마), `seo-report.html`을 저장합니다. 보고서는 영업 담당자 요약·우선순위, 기술 담당자 전체 근거 펼쳐보기, 분석 실패, 미검증, 고객 질문, 환경별 검토 참고를 구분합니다. 기존 `intake.json`/`environment.json`/사전 검토 파일은 그대로 보존하며 과거 환경 분석 시점·가상 출처를 표시합니다. 민감값 마스킹·HTML 이스케이프·오프라인 CSP를 적용하고 원본 HTML/쿠키/임의 헤더는 저장하지 않습니다. 산출물은 기존 프로젝트 `.gitignore`로 Git에서 제외합니다.

`COMPLETE`는 설정한 정적 검사 완료, `PARTIAL`은 분석 페이지는 있으나 검사 한도·미검증·실패가 있음, `BLOCKED`는 동의/URL/접근 문제로 분석한 HTML이 없음입니다. SEO 문제가 있다는 이유로 명령이 실패하지는 않습니다(저장 성공 0, BLOCKED/입력·저장 오류 1, 인자 오류 2). 재실행 전 결과는 `history/seo-*`에 백업합니다. 복원하려면 이전 `seo-audit.json`/`seo-report.html`을 프로젝트 폴더에 복사하세요. 소스 수정 전 백업은 `results/step3/baseline-backup.zip`에 있으며 해당 파일만 복원하고 새 `seo_*.py`·테스트·재현 스크립트를 제거하면 STEP 2로 되돌릴 수 있습니다. 고객 사이트 복구 작업은 발생하지 않습니다.

### 실제 네트워크 없이 가상 프로젝트부터 HTML까지 재현

```powershell
.\.venv\Scripts\python scripts/step3_demo.py
.\.venv\Scripts\python -m environment_detector project audit customer-data/projects/JOB-DEMO-SEO --report-only
.\.venv\Scripts\python -m pytest -q
```

재현 스크립트는 기존 가상 병원 입력을 복사해 **모의 동의·고정 HTML·MockTransport·모의 DNS**만 사용합니다. 실제 사이트에 접속하지 않으며 기존 STEP 2 가상 프로젝트를 바꾸지 않습니다. 2페이지와 robots/사이트맵으로 JSON·HTML을 만들고 상단에 가상 테스트임을 표시합니다. 결과: `customer-data/projects/JOB-DEMO-SEO/seo-report.html`. 동일 ID가 있으면 `--job-id JOB-DEMO-SEO-2` 등 새 ID를 사용하세요. 가상 결과를 실제 고객 검증으로 사용하지 않습니다.

재현 프로젝트에는 `data_origin: SYNTHETIC_TEST_FIXTURE`를 표시합니다. 이 프로젝트의 모의 동의로 일반 `audit`의 실제 HTTP 분석을 허용하지 않습니다. 실제 접수는 별도 의뢰서와 동의로 생성해야 합니다.

검사 근거는 [Naver robots 지침](https://searchadvisor.naver.com/guide/seo-basic-robots), [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html), [사이트맵 프로토콜](https://www.sitemaps.org/protocol.html), [Google Search Central](https://developers.google.com/search/docs), [W3C 접근성 지침](https://www.w3.org/WAI/tutorials/), [schema.org ItemList](https://schema.org/ItemList), [Open Graph](https://ogp.me/)를 참조하며 각 검사에 해당 세부 문서 링크를 저장합니다. Google 고유 지원 동작을 Naver의 동작으로 간주하지 않습니다.

## STEP 2: 고객 의뢰 접수·프로젝트 생성·사전 견적 검토

기존 [최초 의뢰서](templates/01_customer_inquiry_quote.md)와 [내부 수주 체크리스트](templates/03_internal_intake_review.md)를 기준으로 JSON 입력 필드를 정리했습니다. 고객에게 Markdown/JSON 문법을 강제하는 웹 폼은 만들지 않았습니다. 담당자가 받은 신청서 내용을 아래 JSON 예제에 옮겨 CLI에 입력합니다. CMS를 모르면 null로 접수할 수 있습니다. 담당자 이름·연락처·비밀번호·환자정보는 이 입력에 수집하지 않습니다.

### 가상 병원 1건 재현 (사이트 요청 없음)

```powershell
.\.venv\Scripts\python -m environment_detector project create templates/examples/hospital-intake.json --environment templates/examples/hospital-environment.json --job-id JOB-DEMO-HOSPITAL
.\.venv\Scripts\python -m environment_detector project review customer-data/projects/JOB-DEMO-HOSPITAL
```

결과는 `customer-data/projects/JOB-DEMO-HOSPITAL/report.html`입니다. 이번 예제는 실제 병원·실제 사이트 분석 결과가 아닌 **가상 입력과 가상 탐지 JSON**이며, HTML에도 출처를 명시합니다. 공개 분석 동의가 false이고 화면 유형이 미검토여서 `NEED_INFO`가 정상입니다. 같은 ID가 이미 있으면 덮어쓰지 않고 종료 코드 1을 반환하므로 다시 생성할 때는 `--job-id`를 생략해 새 자동 ID를 받으세요. `review`는 기존 폴더의 오프라인 재검토이며 사이트에 재요청하지 않습니다.

가상 출처(`data_origin: SYNTHETIC_TEST_FIXTURE`, 설명이 붙은 값 포함)는 보고서 상단과 기술 항목에 표시합니다. 가상 신뢰도는 실제 평가 점수로 표시하지 않고, 원본 JSON의 값은 보존합니다. 가상 기술 단서는 실제 CMS 대조·환경 검증에 사용하지 않으며, 실제 관찰 결과가 없으면 해당 검토를 내부 작업으로 남겨 READY 처리하지 않습니다.

### 실제 접수 명령

실제 입력은 Git 제외 경로인 `customer-data/intake/customer.json` 등에 보관합니다. 폴더와 파일을 만들고 가상 의뢰 JSON의 필드를 실제 접수 내용으로 작성한 후 실행합니다.

```powershell
# 같은 URL의 기존 JSON 파일을 명시적으로 재사용
.\.venv\Scripts\python -m environment_detector project create customer-data/intake/customer.json --environment results/customer.json

# 폴더에서 동일 URL의 가장 최근 성공 결과 재사용 (없으면 최신 오류 결과)
.\.venv\Scripts\python -m environment_detector project create customer-data/intake/customer.json --reuse-dir results

# 고객이 공개 영역 분석에 명시적으로 동의한 경우에만 새 분석 요청
.\.venv\Scripts\python -m environment_detector project create customer-data/intake/customer.json --analyze
```

환경 소스 옵션을 생략하면 `results` 바로 아래에서 캐시를 찾는 **오프라인 접수**입니다. 캐시가 없어도 자동으로 사이트를 요청하지 않습니다. `--analyze`는 새 분석을 명시적으로 선택하며 캐시 탐색과 함께 사용하지 않습니다. 이때 의뢰서의 `public_analysis_consent`가 JSON boolean `true`여야 합니다. false/null/문자열 `"true"`는 동의로 인정하지 않으며, 요청 없이 미분석 JSON과 NEED_INFO 검토를 저장합니다. 대상·참고 URL이나 스크린샷을 자동으로 열지 않습니다. 새 분석도 홈페이지 URL 한 개만 기존 Detector의 SSRF·요청 제한으로 분석합니다.

기존 결과는 정규화한 URL의 스킴·호스트·경로·쿼리가 같은 경우에만 연결합니다. `www`나 다른 경로의 결과를 대신 붙이지 않습니다. 명시한 환경 JSON이 다른 URL이거나 잘못된 형식이면 생성하지 않습니다. 캐시 검색에서는 잘못된 파일·다른 URL·심볼릭 링크 파일을 건너뜁니다. 분석 시각과 경과 일수를 보존하고 **30일 초과·시각 불명·미래 시각**에는 확인 질문을 남깁니다. 오래되었다고 자동 갱신하지 않습니다.

### 정규화 JSON 필드

`templates/examples/hospital-intake.json`이 실행 가능한 전체 입력 예제입니다. 기술 정보를 모른다고 접수 자체를 거절하지 않으며, 누락·형식 오류는 검토 질문으로 남깁니다. JSON 문법 자체가 잘못되었거나 객체가 아니면 CLI 오류입니다.

| JSON 키 | 의뢰서 항목 |
| --- | --- |
| `company_name`, `industry`, `site_url` | 업체명·업종·홈페이지 URL |
| `reported_cms` | 고객이 아는 구축 방식 (선택, null/모름 허용) |
| `requested_services` | `carousel`, `seo`, `images` 배열. 네이버 캐러셀·SEO·이미지 최적화도 허용 |
| `target_queries` | 원하는 검색어 배열 |
| `reference_result` | `urls`, `screenshots` 자료명 배열, `device`, `description`. 자료는 저장된 문자열로만 취급 |
| `content_type`, `target_page_urls` | 의료진·진료과목·제품·시공 사례 등 표시 대상과 작업 페이지 배열 |
| `content_available`, `images_available`, `content_usage_rights` | `yes`/`no`/`partial`/`unknown`. 사용 권한은 고객 확인 진술 |
| `modification_owner`, `modification_route` | 수정 권한 보유자 역할·협의할 작업 경로. 실제 권한 검증이나 배포 승인이 아님 |
| `content_review_owner` | 의료 콘텐츠 등을 게시 전 검토할 고객 담당 역할 (해당 시) |
| `desired_schedule`, `additional_requests` | 희망 일정·추가 요청. 비용·납기 자동 확정 없음 |
| `public_analysis_consent` | 해당 홈페이지 공개 영역 분석에 대한 true/false/null |

인증정보가 포함된 URL, 사설 IP·위험 URL은 새 분석하지 않습니다. 대상 페이지가 홈페이지와 다른 호스트이면 작업 범위 질문을 남깁니다. 정규화는 DNS를 조회하지 않으며 실제 HTTP 직전에 기존 Detector가 DNS 전체와 연결 목적지를 다시 검사합니다.

### 판정과 담당자 검토 기록

- **READY:** 기본 의뢰 정보·콘텐츠·수정 담당/협의 경로 및 공개 환경 단서가 있어 견적 검토 가능. 실제 권한·운영 배포 가능성을 확정하지 않습니다.
- **NEED_INFO:** 정보·동의·콘텐츠·권한 확인이 부족하거나 환경 미식별/오류·오래된 분석·서로 다른 CMS 단서가 있음. 자체 개발로 추측하지 않습니다.
- **CUSTOM_QUOTE:** 누락 확인 후, 고객의 자체 개발 진술·프레임워크 빌드 단서·별도 복잡성 검토 등에 따라 개별 기술 견적이 필요함. 진술과 관찰의 출처는 분리합니다.
- **OUT_OF_SCOPE:** 명시한 요청이 지원 서비스에 없거나, 캐러셀만 요청했으나 담당자 검토 기록상 참고 화면이 다른 검색 기능임. SEO 등 다른 요청이 섞이면 범위 재협의 질문으로 남깁니다.

캐러셀 요청의 화면 유형은 고객 설명이나 기술 탐지로 확정하지 않습니다. 담당자가 참고 자료를 검토한 뒤 [검토 기록 예제](templates/examples/operator-review.json)를 `customer-data/reviews/`에 복사해 `reviewer_role`, `evidence`, `search_result_type`을 작성합니다. 유형은 `unknown/carousel/sitelinks/place/ad`이며 실제 판정을 기록하려면 역할·근거가 모두 필요합니다. 복잡한 연동을 검토한 경우에만 `complex_environment: true`와 근거를 기록합니다. 고객 의뢰 JSON에 검토 필드를 끼워 넣어도 담당자 확인으로 인정하지 않습니다.

```powershell
.\.venv\Scripts\python -m environment_detector project review customer-data/projects/JOB-DEMO-HOSPITAL --review-notes customer-data/reviews/staff-review.json
```

담당자 기록 역시 프로그램이 화면을 검증한 사실은 아닙니다. 고객 CMS 진술은 `intake.json`, 탐지 결과는 `environment.json`에 각각 보존하며 서로 달라도 덮어쓰지 않습니다.

질문 목록은 기존 배열 구조를 유지하면서 `audience: customer`(고객 질문) 또는 `internal`(내부 담당자 작업)을 기록합니다. HTML도 두 목록을 구분합니다. 검색 화면 유형 판단·분석 시점 검토·가상 결과 대체 확인은 내부 작업입니다.

고객의 `reference_result.screenshots`는 **자료명**이며 실파일 확보 증거가 아닙니다. 참고 URL도 없고 자료명만 있으면 고객에게 실제 파일/URL 전달을 요청하고 내부 수령 확인 작업을 남깁니다. 파일을 확보한 담당자는 검토 JSON의 `screenshot_files`에 로컬 이미지 파일의 절대 경로 배열을 기록할 수 있습니다(역할·근거 필수). 프로그램은 로컬 실파일의 존재·비어 있지 않음만 확인하며 이미지 내용을 열거나 분석하지 않습니다. 상대 경로·URL·UNC·심볼릭 링크/정션은 확보 증거로 인정하지 않습니다. 파일이 존재해도 화면 유형은 담당자 별도 검토가 필요하며 재검토 시 파일이 사라졌다면 다시 미확인으로 처리합니다.

### 산출물·개인정보·되돌리기

기본 작업 폴더는 `customer-data/projects/JOB-시각-임의ID/`이며 `--projects-dir`로 바꿀 수 있습니다. 업체명·전화번호를 작업 ID에 넣지 않습니다. stdout은 ID·판정·질문 수·HTML 경로의 JSON 요약입니다. 생성·재검토 성공은 판정 종류와 무관하게 종료 코드 0, 입력/저장/중복 ID 실패는 1, 인자 오류는 2입니다.

| 파일 | 내용 |
| --- | --- |
| `project.json` | 작업 ID·접수 시각·분석 출처·별도 담당자 기록 |
| `intake.json` | 정규화한 고객 진술과 입력 검증 질문 |
| `environment.json` | 기존 1.0 스키마를 유지한 탐지 결과 복사 또는 미분석/오류 결과 |
| `review.json`, `questions.json` | 판정·근거·가능 작업·추가 권한·질문 목록 |
| `report.html` | 기존 보고서 UI·근거 펼쳐보기를 재사용한 한국어 사전 검토 보고서 |
| `.gitignore`, `history/` | 커스텀 출력 위치에서도 산출물 Git 제외, 재검토 전 버전 백업 |

출력은 알려진 인증 키·쿠키·비밀번호·URL 쿼리·프래그먼트·이메일·전화번호를 마스킹하고, 입력의 불필요한 연락처/인증 키는 보관하지 않습니다. HTML은 이스케이프하고 외부 스크립트·이미지를 로드하지 않습니다. 모든 개인정보를 자동 식별하는 기능은 아니므로 이름·환자정보·비밀을 자유 텍스트에 넣지 마세요. 실제 입력 원본도 `customer-data/` 등 Git 제외 경로에 보관하고 접근·보존·삭제 정책을 별도로 관리하세요. Git 제외는 암호화나 OS 접근 제어가 아니며 강제 추가(`git add -f`)를 막지 않습니다.

재검토는 입력 의뢰·환경 JSON을 바꾸지 않고, 이전 `project.json/review.json/questions.json/report.html`을 `history/`에 백업한 뒤 갱신합니다. 파일별 저장은 임시 파일로 교체하며 다중 파일 DB 트랜잭션은 아닙니다. 복원은 해당 history 버전의 네 파일을 작업 폴더에 복사하면 됩니다. STEP 2 구현 전 파일 백업은 `results/step2/baseline-backup.zip`입니다. 코드 되돌리기는 이 백업의 `cli.py`, README, .gitignore를 복원하고 이번에 추가한 접수·프로젝트 모듈/테스트/예제만 제거합니다. 운영 사이트 변경은 없으므로 사이트 롤백은 없습니다.

STEP 1.2의 OPTIONAL 판정은 유지하며 외부 탐지 엔진은 호출하지 않습니다. 이 단계는 수주 전 정리와 검토만 제공하고, SEO 수정·캐러셀 적용·이미지 처리·배포는 수행하지 않습니다.

검증 결과: STEP 2 최초 **244개**를 유지하고 가상 출처·질문 대상 구분·실파일 확보·한국어 과잉 마스킹 수정의 회귀 테스트 **28개**를 추가하여 **272 passed**입니다. 기존 Environment Detector·CLI 테스트도 포함합니다. 실제 CLI로 가상 병원 접수 → HTML 생성 → 재검토 → 중복 ID 거절을 재현했습니다. 수정 전 코드·산출물은 `results/step2-fixes/before-fixes.zip`, 재검토 전 산출물은 프로젝트 `history/`에 보존합니다. 복원 시 백업의 해당 기존 파일만 되돌리면 됩니다.

## STEP 1.2: 외부 엔진 비교 검증 (종료)

ProjectDiscovery httpx v1.12.0(MIT)을 별도 `pd-httpx.exe`로 준비해 지정 공개 사이트 5곳만 비교했습니다. 판정은 **OPTIONAL**입니다. 자원·엣지 탐지 범위는 넓지만 CMS/프레임워크 누락과 연쇄 추정·오탐 후보가 있어 핵심 엔진에는 통합하지 않았습니다. 기존 Python httpx 패키지·CLI·JSON은 그대로입니다.

비교표·근거·분석 시간·Windows 준비 방법은 [간단 비교 기록](docs/step1.2-comparison.md), 생성된 HTML은 `results/step1.2/comparison.html`입니다. 저장 결과만으로 재생성하려면 `.\.venv\Scripts\python scripts/step1_2_report.py`를 실행합니다. 이 명령은 사이트를 재요청하지 않습니다. 당시 STEP 1.2 검증은 147개 기존 회귀와 비교 검증 15개를 합쳐 162개가 통과했습니다. 현재 전체 회귀는 아래 테스트 절과 [프로젝트 상태](docs/PROJECT_STATE.md)를 참조하세요. 비교 회귀의 입력은 순수 합성 자료이며 새 실사이트 측정이 아닙니다.

## STEP 1.1: 저장된 JSON → HTML 보고서

```powershell
.\.venv\Scripts\python -m environment_detector report ./results -o ./results/report.html
```

`results/report.html`을 브라우저에서 직접 열면 됩니다. 새 서버나 추가 프런트엔드 설치가 필요 없습니다. **보고서 생성은 저장된 JSON만 읽으며 사이트·DNS·외부 자원을 재요청하지 않습니다.** 기존 URL 분석 명령과 JSON 스키마 1.0은 그대로 유지합니다.

- 폴더 바로 아래의 `.json` 파일을 파일명 순서로 종합합니다(하위 폴더·ZIP은 읽지 않음). JSON 파일 하나를 직접 지정할 수도 있습니다. 중복 사이트도 파일별로 보존합니다.
- `-o` 생략 시 입력 폴더 또는 입력 파일 옆에 `report.html`을 저장합니다. 출력은 `.html`만 허용하며 같은 HTML 경로는 교체합니다. JSON 입력은 수정하지 않습니다.
- 파일별 상태는 **단서 있음 / 기술 미확인 / 분석 오류 / 보안 차단 / JSON 입력 오류**로 구분합니다. 기술 미확인은 정상 결과에서 CMS·프런트엔드·백엔드가 모두 UNKNOWN인 경우이며, 서버·CDN 단서는 별도 표시합니다.
- 아임웹·카페24 자원은 **후보 · 미확정**입니다. 점수나 자원 개수가 늘어도 플랫폼 확정으로 승격하지 않습니다. WordPress generator는 **명시 표기 확인**, Next.js 자원은 **빌드 자원 확인**으로 표현하며 실제 서버 운영 환경의 확정을 뜻하지 않습니다.
- HTTP 응답 서버, CDN, 원본 서버를 분리합니다. 기존 JSON의 `Server: CloudFront`만으로 CDN UNKNOWN을 바꾸지 않으며, 원본 서버와 자체 개발 여부는 UNKNOWN으로 표시합니다.
- 주요 근거를 먼저 설명하고, **전체 근거 펼쳐보기**에서 저장된 모든 근거의 규칙·위치·값·원문 설명·참고 자료를 확인합니다. ‘전체’는 최초 JSON에 저장된 범위입니다. 마스킹된 전체 JSON도 펼쳐볼 수 있습니다.
- HTML은 UTF-8 단일 파일입니다. 입력 문자열을 HTML 이스케이프하며, 외부 링크·실행 스크립트·외부 CSS·이미지를 만들지 않습니다. CSP로 외부 자원 로드를 차단합니다. 참고 URL은 텍스트로 표시합니다.
- URL 사용자 정보, 모든 쿼리·프래그먼트 값, 알려진 비밀번호·토큰·API 키·쿠키·인증 헤더 등을 보고서와 요약에서 마스킹합니다. 터미널 제어 문자도 제거합니다. 원본 JSON은 마스킹하지 않으므로 따로 보호해야 합니다. 이름을 알 수 없는 자유 텍스트·경로·파일명 속 비밀까지 완전히 식별할 수는 없어 외부 공유 전에 검토하세요.
- 파일당 5 MiB, UTF-8(선택적 BOM), 스키마 1.0과 기술·근거·오류 필드 형식을 검증합니다. 잘못된 JSON은 해당 파일의 입력 오류 카드로 남기고 나머지 파일은 계속 처리합니다. 심볼릭 링크 JSON은 거절합니다.
- 보고서와 터미널에 파일별 결과 및 종합 개수를 출력합니다. 저장된 분석 오류·보안 차단도 유효한 보고서 항목이므로 생성 성공 시 종료 코드 `0`입니다. JSON 입력 오류가 하나라도 있거나 보고서 생성·저장에 실패하면 `1`, 잘못된 인자는 `2`입니다. JSON 입력 오류가 섞인 경우에도 나머지 결과를 담은 HTML은 저장합니다.

기존 URL 분석에 터미널 요약을 추가하려면 다음처럼 실행합니다. **stdout과 저장 파일은 기존 JSON 그대로**, 마스킹된 요약만 stderr에 출력합니다. `--summary`를 생략하면 기존 출력 동작과 같습니다.

```powershell
.\.venv\Scripts\python -m environment_detector "https://example.com/" -o results/customer.json --summary
```

7개 저장 결과의 근거 검토는 [docs/step1.1-evidence-review.md](docs/step1.1-evidence-review.md)에 정리했습니다. 보고서 생성 시각과 원본 분석 시각은 별도이며, 최신 사이트 상태를 재검증한 결과가 아닙니다.

## 설치 및 실행

Python 3.11 이상이 필요합니다. Windows PowerShell에서 프로젝트 루트를 기준으로 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
.\.venv\Scripts\python -m environment_detector "https://example.com/" -o results/customer.json
```

설치된 실행 파일로도 사용할 수 있습니다.

```powershell
.\.venv\Scripts\environment-detector "https://example.com/"
```

Linux/macOS에서는 `.venv/bin/python`, `.venv/bin/environment-detector`를 사용합니다. 별도 API 키는 없습니다.

- URL은 `http://` 또는 `https://`를 포함해야 합니다.
- stdout에는 JSON만 출력합니다. `-o` 생략 시 `results/environment.json`에 UTF-8 JSON을 저장합니다. 상위 폴더는 자동 생성하며 같은 경로의 파일은 덮어씁니다.
- 성공 종료 코드는 `0`, 탐지 요청·저장 실패는 `1`, CLI 인자 오류는 argparse 기본값인 `2`입니다.
- 네트워크/안전성 오류에도 `status: "error"`, `errors[].code`를 포함한 JSON을 출력·저장합니다. 파일 저장 자체가 실패하면 stdout JSON과 stderr 진단을 제공합니다.
- 다른 호스트로 이동하는 사이트는 차단합니다. `example.com` → `www.example.com`도 해당합니다. 최종 호스트의 URL이 승인 범위인지 확인한 후 해당 URL을 직접 입력하세요.

## 탐지 결과와 해석

`technologies`는 `cms`, `frontend`, `backend`, `server`, `cdn` 배열로 구성됩니다. 같은 범주에서 복수 후보를 보존하며 각 후보에는 `name`, `confidence`, `evidence`가 있습니다. `evidence`는 규칙 ID, 관찰 위치, 관찰 값(최대 300자), 의미와 한계, 공식 참고 자료 URL을 기록합니다. 단서가 없는 범주는 다음과 같습니다.

```json
{
  "name": "UNKNOWN",
  "confidence": 0.0,
  "evidence": []
}
```

상위 필드에는 스키마 버전, UTC 분석 시각, 입력/최종 URL, HTTP 상태, HTML 바이트 수, 리다이렉트 이력, 오류가 포함됩니다. 최종 응답 헤더는 `content-type`, `server`, `x-powered-by`, `cf-ray`만 저장합니다. 전체 HTML과 쿠키는 저장하지 않습니다. 입력 URL의 쿼리 문자열과 관찰된 자원 URL은 결과에 남을 수 있으므로 인증 정보가 포함된 URL을 입력하지 마세요.

| 범주 | 관찰 규칙 | 신뢰도 |
| --- | --- | --- |
| CMS / WordPress | generator 메타 태그의 명시적 WordPress 표기 | 0.95 |
| CMS / WordPress | 자원 경로의 `/wp-content/themes/`, `plugins/`, `uploads/` | 0.65 |
| CMS / Imweb | 자원 호스트가 정확히 `cdn.imweb.me` | 0.55 |
| CMS / Cafe24 | 자원 호스트가 정확히 `img.echosting.cafe24.com` | 0.55 |
| Frontend / Next.js | script/link 자원 경로가 `/_next/static/`로 시작 | 0.80 |
| Frontend / Next.js | `X-Powered-By: Next.js` | 0.90 |
| Backend / Express, PHP | `X-Powered-By: Express` 또는 `PHP[/버전]` | 0.90 |
| Server | 공개 `Server` 헤더 값 그대로 | 0.90 |
| CDN / Cloudflare | 형식이 맞는 `CF-Ray` 응답 헤더 | 0.90 |

점수는 규칙 강도이며 통계적으로 보정된 확률이 아닙니다. 동일 기술의 여러 단서는 가장 높은 점수를 사용하고 근거를 합칩니다(기술당 최대 10개). 헤더도 위장할 수 있습니다. 이미지 등 외부 자원 하나로 플랫폼을 확정할 수 없어 아임웹·카페24 자원 규칙은 후보 수준으로 기록합니다. 호스트는 URL 파싱 후 정확히 비교하므로 `cdn.imweb.me.attacker.com` 같은 이름은 매칭하지 않습니다. 일반 본문, 주석, `#root`, `.php` 확장자, 일반 `/assets/` 경로는 기술 근거로 사용하지 않습니다.

**자체 개발 여부(`development_model`)는 UNKNOWN**입니다. 알려진 CMS 단서가 없다는 이유로 자체 개발로 분류하지 않습니다. 자체 개발 사이트에서도 명시적인 Express/PHP 헤더나 Next.js 빌드 자원이 있으면 해당 기술만 탐지합니다. WordPress → PHP, Next.js → Node.js/React처럼 서버 내부 기술이나 추가 프레임워크를 추정하지 않습니다. `Server`는 응답한 프록시/엣지일 수 있으며 원본 서버를 확정하지 않습니다.

규칙의 공식 근거는 [docs/detection-rules.md](docs/detection-rules.md)에 정리했습니다.

## 네트워크 안전성 및 범위

- HTTP(S), 포트 80/443만 허용합니다. URL 사용자 정보, 제어 문자, 역슬래시, 로컬/특수 호스트 이름을 차단합니다. 사설망 접근 우회 옵션은 제공하지 않습니다.
- DNS의 모든 A/AAAA 결과를 검사하고 하나라도 비공개 주소이면 차단합니다. 루프백·사설·링크 로컬·공유 주소·예약·멀티캐스트와 IPv4 매핑/전환 IPv6, 알려진 메타데이터 주소를 차단합니다.
- DNS 검사 후 선택한 공인 IP로 연결을 고정합니다. 원래 Host와 SNI를 유지하고 TLS 인증서를 검증합니다. DNS 재조회로 사설 IP에 연결되는 재바인딩을 방지합니다.
- 환경 프록시와 `.netrc`는 사용하지 않습니다(`trust_env=False`). 리다이렉트마다 새 클라이언트를 사용하므로 쿠키를 전달하지 않습니다.
- 같은 호스트의 리다이렉트만 최대 3회 허용합니다(총 최대 4개 GET). 매번 URL과 DNS를 검사하고 HTTPS에서 HTTP로의 하향 이동을 차단합니다. 자동 재시도·추가 페이지·관리자 경로·외부 자원 요청은 없습니다.
- HTTP 작업별 타임아웃은 최대 10초, 전체 작업은 30초 예산을 두고 연결 전과 본문 수신 중 확인합니다. OS DNS 조회는 동기 호출이므로 OS의 DNS 타임아웃에 따라 30초를 초과할 수 있습니다. 진행 중인 네트워크 호출도 남은 예산 또는 작업별 타임아웃까지 기다릴 수 있어 엄격한 프로세스 종료 제한은 아닙니다.
- HTML 본문은 최대 2 MiB입니다. 압축 폭탄을 피하기 위해 `Accept-Encoding: identity`를 요청하며, 압축 응답을 강제로 보내는 서버는 `UNSUPPORTED_ENCODING`으로 거절합니다.

## 테스트

```powershell
.\.venv\Scripts\python -m pytest -q
```

테스트는 DNS와 HTTP 응답을 모의 처리하며 실제 고객 사이트나 내부망에 접속하지 않습니다. 탐지 근거/신뢰도, UNKNOWN, 오탐 방지, IP 고정·Host/SNI, DNS 재바인딩, 위험 URL/주소/리다이렉트, HTTP/TLS·타임아웃 오류, 본문 크기, JSON 파일/stdout 및 저장 실패를 검증합니다. 실제 인터넷 TLS 연결이나 모든 CMS 버전에 대한 호환성을 검증하는 테스트는 아닙니다.

STEP 1.1 테스트는 사람이 구성한 합성 JSON 7개(`tests/fixtures/synthetic/step1`)로 후보/표기 구분과 전체 근거 42개 보존을 검증합니다. 원래 저장된 분석 JSON 8개는 로컬에 보존하고 Git에서 제외하며 테스트는 읽지 않습니다. STEP 1.2 비교용 합성 snapshot 1개까지 포함한 구성·고정 URL 유지 이유·구형 출처 없는 스키마 분기 검증은 [fixture 출처](tests/fixtures/synthetic/README.md)에 명시했습니다. 합성 자료의 상태·신뢰도는 실제 고객 검증이 아닙니다. 보고서 실행 중 HTTP/DNS 접근 시 즉시 실패하도록 막고, XSS·마스킹·잘못된 JSON·출력 실패·원본 보존을 확인합니다. 실제 `python -m environment_detector` 프로세스로 보고서 및 기존 보안 차단 CLI 회귀도 검사합니다.

## 완료 범위와 한계

STEP 1의 CLI·환경 탐지·JSON·보고서, STEP 2의 고객 프로젝트·사전 검토, STEP 3의 읽기 전용 SEO 분석을 구현했습니다. SEO 수정, 캐러셀 생성, 이미지 처리, 배포는 구현하지 않았습니다.

단일 최종 HTML 응답만 분석하므로 JS 렌더링 뒤 나타나는 단서, 숨겨진 헤더, 변경된 자원 경로, 지원하지 않는 프레임워크는 UNKNOWN일 수 있습니다. HTML/XHTML Content-Type을 명시한 2xx 응답만 분석하며 4xx/5xx 차단 페이지는 환경 탐지에 사용하지 않습니다. 공인 DNS 결과 중 첫 IP만 연결하며 실패 시 다른 IP로 자동 재시도하지 않습니다. 압축 강제 서버, 타 호스트 리다이렉트는 의도적으로 지원 범위를 제한했습니다. 공개 단서는 실제 운영 백엔드·원본 인프라·호스팅·OS·DB·자체 개발 여부를 증명하지 않습니다.
