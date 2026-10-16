# 합성 회귀 fixture 출처

이 폴더의 JSON 8개는 모두 **SYNTHETIC_TEST_FIXTURE**다. 사람이 테스트 계약을 보고 최소 시나리오를 새로 구성했다. 실사이트·고객 HTTP 요청, 브라우저, 외부 엔진을 실행하거나 기존 분석 JSON의 본문·측정값을 복사하지 않았다. 가상 데이터는 실제 고객 검증이나 최신 사이트 상태의 증거가 아니다.

## 구성

| 경로 | 의도적으로 구성한 입력과 기대 계약 |
| --- | --- |
| step1/wordpress_nasa.json | 버전 없는 WordPress generator + 가상 테마 자원 9개. CMS 근거 10개·규칙 강도 0.95, backend UNKNOWN |
| step1/imweb_gilnmi.json | 가상 Imweb 이미지 자원 5개. CMS 후보 유지, 공개 Server CloudFront와 CDN UNKNOWN 분리 |
| step1/cafe24_demo.json | 가상 Cafe24 이미지 자원 9개. CMS 후보 유지, 공개 Server openresty |
| step1/nextjs_official.json | 가상 Next.js 빌드 자원 10개. frontend만 식별, CMS/backend UNKNOWN |
| step1/unknown_example.json | 정상 응답, 가상의 Cloudflare 서버·응답 마커만 있음. CMS/frontend/backend UNKNOWN |
| step1/customer.json | 예약 도메인 customer.example의 정상 미식별 시나리오. 실제 고객 자료 아님 |
| step1/blocked-smoke.json | 사설 목적지 차단 오류를 수동 구성. 실제 연결·DNS 없음, 모든 기술 UNKNOWN |
| step1_2/snapshot.json | 비교 로더에 필요한 5개 대상과 최소 외부 기술 배열만 수동 구성. PHP/MySQL implies·CDN 부재·Next.js 누락·OPTIONAL/보류 분기 검증 |

기존 집계 계약인 7개 결과·기술 항목 35개·근거 행 42개를 보존하도록 최소 입력을 구성했다. CMS/프런트엔드 근거는 10+5+9+10개, 서버 근거 6개, 가상 CDN 마커 근거 2개다. 각 환경 JSON의 fixture_input은 사람이 구성한 입력이며 tests/test_synthetic_fixtures.py가 실제 analyze 함수로 재계산해 저장 근거와 정확히 대조한다. linked resource는 요청하지 않는다.

실제 응답 본문·실제 버전·청크 해시·추적 ID·사용자 경로는 포함하지 않는다. 자원 경로의 synthetic-fixture는 가상 식별자다. 두 CF-Ray 값은 0 또는 1만 반복하고 TST로 끝나는 의도적 가짜 마커다. 분석 시각은 null, 비교 시각은 SYNTHETIC_NOT_MEASURED, 외부 버전은 SYNTHETIC_NOT_EXECUTED, 소요 시간 0은 미측정 자리표시자다. size_bytes는 가상 HTML의 UTF-8 길이이며 네트워크 측정값이 아니다.

## 역사적 이름과 URL을 유지하는 이유

5개 비교 대상의 이름·URL은 변경 금지된 scripts/step1_2_collect.py의 TARGETS와 scripts/step1_2_report.py의 REVIEWS 조회 키다. 이를 그대로 유지하는 것은 고정 범위·매칭·OPTIONAL 판정의 호환성 계약을 검사하기 위해서다. 실제 사이트를 이번에 관찰했다는 뜻이 아니다. blocked-smoke의 사설 IP는 SSRF 차단 입력이다. customer는 비교 계약 밖이므로 예약 도메인으로 구성했다.

비교 스크립트의 REVIEWS/COMMON에는 이전 실험의 수동 해석과 실제 버전·자원 문자열이 코드 상수로 남아 있다. 이번 허용 범위에서는 프로그램/스크립트를 수정하지 않는다. 합성 snapshot에서 생성한 비교 HTML/JSON에도 그 과거 고정 문구가 붙을 수 있으므로 **테스트용 출력이며 새로운 측정 또는 독립 실사이트 검증으로 사용하면 안 된다.** 외부 tech 배열은 검증된 정답표가 아닌 분기 입력이다. 과거 실험 설명은 docs/step1.2-comparison.md에 별도 보존한다.

## 기존 검증 의도와 출처 분리

- tests/test_report.py와 tests/test_step1_2_comparison.py는 이 폴더만 읽는다. 후보/명시 표기 판정 함수, UNKNOWN, 근거 전량 보존, 오류/차단, 출력 형식·마스킹/XSS, OPTIONAL/평가 보류 assert를 유지한다. 합성 보고서에서는 경고와 가상 라벨을 기대한다.
- tests/conftest.py의 legacy_environment는 별도 손 작성한 최소 입력을 analyze로 구성한다. 구형 schema 1.0의 data_origin 미제공 분기를 테스트하기 위해 그 필드를 처음부터 넣지 않는다. 합성 JSON의 marker를 제거하거나 OBSERVED_HTTP로 덮어쓰지 않는다. tests/test_projects.py와 tests/test_workbench.py는 고정 테스트 시계를 지정해 READY·COMPLETED 등 기존 호환성 분기를 유지한다. 이 상태 assert는 프로그램 동작의 검증이며 실제 고객 완료 판정이 아니다. Workbench의 손 작성 SEO 입력도 출처 없는 구형 형식이며 실제 관찰 표시는 제거했다.
- 실제 marker가 있는 8개 JSON은 항상 합성으로 남는다. 추가 회귀는 출처·미측정 자리표시자·8개 목록·탐지 근거 재계산·보고서 경고·NEED_INFO/NOT_VERIFIED와 독립 fixture 복사본 실행을 검사한다. 전체 테스트의 기본 DNS/소켓 연결을 차단하며 기존 모의 DNS/MockTransport는 유지한다.
- 원래 tests/fixtures/step1/*.json 7개와 tests/fixtures/step1_2/snapshot.json은 로컬 보존·Git 제외 상태다. 테스트는 이 경로로 fallback하지 않는다. 후보 전체 회귀는 실제 Git 후보 파일만 복사한 별도 트리에서 검증한다.
