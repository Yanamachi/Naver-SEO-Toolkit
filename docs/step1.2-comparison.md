# STEP 1.2 — ProjectDiscovery httpx 비교 검증

**판정: OPTIONAL.** 자바스크립트 자원과 엣지 식별을 보조하는 독립 도구로는 가치가 있지만 핵심 엔진 통합의 필요성은 확인하지 못했습니다. 자체 Detector·JSON 스키마·CLI·기존 HTML 보고서는 변경하지 않았습니다.

## 도구 및 Windows 준비

- 공식 릴리스 API에서 확인한 최신 버전은 [v1.12.0](https://github.com/projectdiscovery/httpx/releases/tag/v1.12.0), 공개일은 2026-09-08 UTC입니다. [MIT 라이선스](https://github.com/projectdiscovery/httpx/blob/v1.12.0/LICENSE.md)입니다. 배포 시 저작권·허가 문구 보존이 필요합니다.
- [공식 설치 문서](https://docs.projectdiscovery.io/opensource/httpx/install)의 Binary 방식으로 Windows amd64 ZIP을 받아 해제했습니다. 실행에 Go 설치는 필요하지 않습니다. 소스 빌드는 고정 태그의 [go.mod](https://github.com/projectdiscovery/httpx/blob/v1.12.0/go.mod)가 Go 1.26.0을 지정합니다.
- 공식 `httpx_1.12.0_checksums.txt`와 ZIP SHA-256을 대조한 후 `httpx.exe`를 **`tools/projectdiscovery-httpx/v1.12.0/pd-httpx.exe`**로 복사했습니다. 라이선스는 같은 디렉터리의 `extracted/LICENSE.md`에 보존했습니다. PATH와 pip 패키지는 변경하지 않았습니다.
- ZIP SHA-256: `14d8ccaa2d95ce9365162682f1a2ba3f14d2000bb4bfb0924af65ec5163ae021`.
- 실행 파일 SHA-256: `95129b2771ad64e675a436279bdfb72cbf00000ebab482f045d021fffff6fbeb`. 수집 스크립트에서도 실행 전 이 해시를 확인합니다.
- Python의 `httpx` 0.28.1은 기존 HTTP 클라이언트 의존성입니다. ProjectDiscovery 도구는 별도 Go 실행 파일이며, `pip install httpx` 또는 모호한 `httpx` 명령으로 설치·실행하지 않습니다.

```powershell
# 준비된 외부 도구의 신원 확인: 고객 사이트 요청 없음
.\tools\projectdiscovery-httpx\v1.12.0\pd-httpx.exe -version

# 이미 저장된 비교 결과의 HTML 재생성: 사이트 재요청 없음
.\.venv\Scripts\python scripts/step1_2_report.py
```

바이너리·ZIP·라이선스·체크섬은 로컬 `tools/projectdiscovery-httpx/`에 있으며 Git 제외 대상입니다. 제품 의존성에 추가하지 않았습니다. [공식 옵션](https://docs.projectdiscovery.io/opensource/httpx/usage)에 따라 사용하되 실제 설치된 `-h` 출력도 `results/step1.2/pd-help.txt`에 저장했습니다.

## 실행 범위와 시간

실험은 2026-10-16 **00:41:53~00:42:19 KST**에 순차 1회 수행했습니다. 각 사이트에 자체 Detector 1회, PD 1회로 설정상 루트 GET 총 10개입니다. 자체 리다이렉트 이력은 모두 비어 있고 외부 request 필드는 모두 `GET / HTTP/1.1`입니다. 별도 패킷 캡처는 하지 않았습니다. 문서·배포 파일 조사 요청은 사이트 비교 요청과 별도입니다.

PD 주요 옵션은 `-tech-detect -server -cdn -status-code -response-time -probe -json -include-response -include-response-header -threads 1 -rate-limit 1 -delay 1s -retries 0 -timeout 10 -no-fallback-scheme -x GET -protocol http11`입니다. 리다이렉트 추적 옵션은 사용하지 않았습니다. 같은 UA·Accept·identity 인코딩을 지정했습니다. DNS 전체를 사전 검사하고 `-allow`에 해당 공인 IP만 허용했으며 `-exclude private-ips`와 알려진 메타데이터 IP 차단도 적용했습니다. 환경 프록시를 제거하고 빈 설정·클라우드 인증 비활성화·업데이트 확인 비활성화를 명시했습니다.

적극적 스캔, 포트/경로 탐색, 서브도메인 수집, favicon, 헤드리스 브라우저, JS 실행, TLS/CSP 도메인 확장, 유료 API, WhatWeb은 사용하지 않았습니다. PD의 JSON 모드가 부가 출력하는 WordPress 플러그인도 [저장된 본문 파싱](https://github.com/projectdiscovery/httpx/blob/v1.12.0/runner/wordpress.go)이며 플러그인 경로에 추가 요청하지 않습니다.

| 대상 | HTTP 자체 / PD | CMS·프레임워크 자체 | PD 주요 결과 | HTTP 서버 자체 / PD | PD CDN | 경과 시간 자체 / PD |
| --- | --- | --- | --- | --- | --- | --- |
| nasa.gov | 200 / 200 | WordPress 명시 표기 | WordPress, Gravity Forms, Block Editor, jQuery, GTM; PHP·MySQL은 연쇄 추정 | nginx / nginx | UNKNOWN | 0.624s / 2.820s |
| gilnmi.imweb.me | 200 / 200 | Imweb 후보 | Imweb, Bootstrap·jQuery 등 자원, CloudFront | CloudFront / CloudFront | cloudfront | 0.616s / 2.953s |
| ecudemo159670.cafe24.com | 200 / 200 | Cafe24 후보 | Cafe24 없음; jQuery·OWL·cdnjs·YouTube, Cloudflare·Nginx 연쇄 추정 | openresty / openresty | UNKNOWN | 0.729s / 2.883s |
| nextjs.org | 200 / 200 | Next.js 빌드 자원 | Next.js 없음; React 마크업 후보, p5.js 오탐 후보, Vercel | Vercel / Vercel | UNKNOWN | 0.279s / 2.141s |
| example.com | 200 / 200 | CMS·프런트·백엔드 UNKNOWN | 해당 기술 없음; Cloudflare, HTTP/3 광고 | cloudflare / cloudflare | cloudflare (waf) | 0.622s / 2.121s |

자체 전체 처리 합계는 **2.871s**, PD 프로세스 경과 합계는 **12.917s**입니다. PD 응답 시간은 각각 344ms, 589ms, 563ms, 166ms, 673ms로 별도 기록했습니다. PD 경과에는 시작·지문 초기화와 명시적 1초 pacing이 포함되고 자체 시간은 동일 프로세스의 전체 분석 호출입니다. 두 값을 순수 탐지 엔진 속도나 속도비로 해석하지 않습니다. 단일 순차 표본이며 동일 바이트 응답·반복 실험·독립 정답표를 확보하지 않았습니다. 신뢰도 수치와 정확도 비율은 비교하지 않습니다.

## 자체 Detector가 식별하지 않은 공개 단서

- NASA: Gravity Forms 자원, WordPress Block Editor 클래스, Google Tag Manager 코드. jQuery 관련 경로는 있으나 기본 라이브러리·실행 확인과 구분합니다. 부가 WordPress 목록의 popup-maker·wp-parsely·accessibility-checker도 자원/마크업 수준입니다.
- 아임웹: Bootstrap, Chosen, Lodash, Modernizr, Moment.js, OWL Carousel, Slick, jQuery, jQuery UI 자원 및 Kakao SDK·Naver Analytics 자원. 외부 파일을 불러와 실행한 확인은 아닙니다. 기존 Server 필드의 CloudFront 표기 외에도 저장 응답의 Via·X-Amz-Cf-Id와 PD 연결 IP CDN 분류가 부합하지만 자체 CDN 규칙에는 없습니다.
- 카페24: jQuery 파일명 1.11.0, OWL Carousel, cdnjs 외부 자원, 주석 밖의 YouTube iframe. Lightbox 계열 자원은 있지만 정확한 제품 식별은 보류합니다.
- Next.js: React 계열 마크업(`data-react-aria-pressable`) 후보입니다. React 런타임의 실제 실행 확인은 아닙니다.
- HSTS 헤더(NASA·카페24·Next.js)와 HTTP/3 서비스 광고(Next.js·example.com)는 현재 지원하지 않는 별도 헤더 기능이며 CMS/프레임워크 정답 수에 포함하지 않습니다.

## 외부 도구의 오탐·추정·한계

지문은 httpx v1.12.0의 [고정 의존성](https://github.com/projectdiscovery/httpx/blob/v1.12.0/go.mod)인 [wappalyzergo v0.2.96 규칙](https://github.com/projectdiscovery/wappalyzergo/blob/v0.2.96/fingerprints_data.json)과 [implies 구현](https://github.com/projectdiscovery/wappalyzergo/blob/v0.2.96/fingerprints.go)을 대조했습니다.

- **PHP·MySQL:** WordPress 규칙이 두 기술을 implies합니다. NASA 응답에 직접 PHP 헤더나 DB 관찰 근거가 없어 확인된 기술이나 자체 누락으로 계산하지 않습니다.
- **Cloudflare / 카페24:** cdnjs 지문이 Cloudflare를 implies합니다. 실제 외부 cdnjs 자원은 있지만 대상 사이트 CDN을 확인한 근거는 아닙니다. `cdn_name`도 비어 있습니다. `tech`의 Cloudflare를 사이트 CDN으로 옮기면 오분류합니다.
- **Nginx / 카페24:** OpenResty의 implies입니다. HTTP Server의 openresty 표기는 확인했지만 별도 원본 Nginx 서버를 확인한 것은 아닙니다.
- **Amazon Web Services / 아임웹:** CloudFront의 implies입니다. AWS 엣지 서비스 문맥으로 제한하며 원본 호스팅을 AWS로 단정하지 않습니다.
- **p5.js / Next.js:** `/_next/static/immutable/chunks/0q93co9tqv6p5.js`의 끝부분이 p5.js 정규식과 매칭됩니다. 해시 청크명 충돌에 의한 **오탐 후보**로 제외합니다. 라이브러리 번들을 추가로 요청하지 않았으므로 p5 부재 자체를 증명한 것은 아닙니다.
- **Lightbox / 카페24:** 넓은 파일명 규칙이 `simple-lightbox.jquery.min.js`에도 매칭합니다. 정확한 Lightbox 제품 확인으로 인정하지 않습니다. React 역시 넓은 `data-react` 마크업 근거만 확인했으며 실행은 미검증입니다.
- **CMS·프레임워크 누락:** 이번 응답에서 Cafe24와 Next.js를 출력하지 못했습니다. 아임웹은 vendor-cdn 스크립트 규칙이라 자체의 이미지 근거보다 자원 범위가 넓지만 플랫폼 확정 근거는 아닙니다.
- **HTTP/3:** Alt-Svc 광고만으로 표시됩니다. 이번 연결은 HTTP/1.1이며 HTTP/3 협상을 검증하지 않았습니다.
- **추적 가능성:** PD `tech` 배열에는 항목별 매칭 위치나 implies 구분이 없습니다. 원본 응답·버전 고정 규칙을 별도로 수동 검토해야 합니다. 기본 결과의 CPE·knowledgebase도 독립 검증 근거로 보지 않았습니다.
- **TLS 정책 차이:** 자체는 인증서를 검증하지만 PD가 사용하는 [fastdialer 기본 TLS 설정](https://github.com/projectdiscovery/fastdialer/blob/v0.5.19/fastdialer/default_config.go)은 인증서 검증을 생략합니다. 두 도구의 접근 성공을 동등한 TLS 검증으로 해석하지 않습니다.

전송·HTTP 접근 실패와 기술 미식별은 별도로 처리했습니다. 이번 실제 표본에는 접근 실패가 없고 5개 모두 200입니다. 빈 tech/CDN 필드는 UNKNOWN이며 기술 없음·자체 개발의 정답이 아닙니다. 테스트에는 출력 없음, 타임아웃형 오류, HTTP 403, 200+기술 목록 없음 사례를 별도로 넣었습니다.

## 산출물·회귀·종료

- HTML: `results/step1.2/comparison.html`; 요약 JSON: `results/step1.2/comparison.json`.
- 외부 원본 JSONL: `results/step1.2/projectdiscovery/results.jsonl` (5개 레코드). 사이트별 JSONL·stderr도 보존합니다. 원본 응답에는 쿠키 등 민감값이 있을 수 있어 원본 파일의 무검토 공유를 피하세요. HTML은 입력을 이스케이프·마스킹하고 외부 자원을 로드하지 않습니다.
- 자체 새 JSON 5개 및 같은 GET에서 포착한 응답: `results/step1.2/detector/`. 기존 `results/*.json`은 보존했습니다.
- 정확한 명령·공인 IP·개별 시간: `results/step1.2/measurements.json`. 도구 조사 자료·버전 고정 소스: `source/`, `release.json`, `pd-help.txt`; 무결성 기록: `artifact-sha256.json`.
- 작업 전 코드·테스트·문서 백업: `results/step1.2/baseline-backup.zip` 및 `baseline-sha256.json`. 되돌릴 때 새 실험 스크립트·문서·테스트만 제거하고 README와 .gitignore 변경을 복원하면 됩니다. 기존 핵심 모듈·테스트는 수정하지 않았습니다.
- 수집 스크립트 `scripts/step1_2_collect.py`는 5개 URL 고정의 일회성 실험 도구입니다. 이미 측정 파일이 있으면 재수집을 거부합니다. 핵심 CLI에서 호출하지 않습니다. `scripts/step1_2_report.py`는 오프라인 보고서 전용이며 검토 문구도 이번 표본에 대한 수동 판단입니다.
- 검증: 기존 **147개** 유지, 비교 범위·오프라인 렌더링·접근 상태 분리·HTML 안전성·해시 파일명 충돌 등 **15개** 추가로 **162 passed**. 이는 당시 실행 기록입니다. 현재 스냅샷 회귀는 [사람이 구성한 합성 데이터](../tests/fixtures/synthetic/README.md)를 사용하며 원래 저장 결과를 읽지 않습니다. 고정 대상 이름/URL은 기존 스크립트 조회 계약을 위해 유지합니다. 합성 비교 출력에 포함되는 REVIEWS/COMMON의 과거 문구는 새 관찰 결과가 아닙니다. 현재 전체 검증 결과는 [프로젝트 상태](PROJECT_STATE.md)를 참조하세요.

현재 필수 CMS/프레임워크 탐지와 근거 설명 요구를 대체할 이유는 부족합니다. 라이브러리/엣지 단서가 필요할 때 별도 보조 확인용으로만 선택할 가치가 있습니다. **OPTIONAL 판정으로 비교 검증을 종료하며, 외부 엔진은 통합하지 않습니다.**
