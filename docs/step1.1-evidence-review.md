# STEP 1.1 — 기존 JSON 7개 근거 검토

검토 대상은 `results` 폴더의 JSON 7개입니다. 사이트를 재요청하거나 버전 표기의 진위를 외부에서 재검증하지 않았습니다. 아래 내용은 **저장된 공개 단서의 해석**이며 기존 JSON과 탐지 규칙은 수정하지 않았습니다. 원래 복사본 `tests/fixtures/step1`은 로컬에 보존하지만 Git에서 제외하며 현재 회귀 테스트는 읽지 않습니다. 현재 회귀는 [순수 합성 fixture](../tests/fixtures/synthetic/README.md)로 같은 후보/근거/UNKNOWN 계약을 검사합니다. 아래 역사적 관찰 해석과 합성 시나리오는 별개입니다.

| 입력 파일 | 기록된 주요 근거 | 보고서 판단 | 서버·CDN 해석 |
| --- | --- | --- | --- |
| `blocked-smoke.json` | `UNSAFE_DESTINATION`, 대상 127.0.0.1 | 보안 차단. 분석 미완료로 기술 부재를 판정할 수 없음 | 모두 UNKNOWN |
| `cafe24_demo.json` | `img.echosting.cafe24.com` 자원 9개, 신뢰도 0.55 | Cafe24 후보 · 미확정. 도메인 이름이나 자원 개수로 플랫폼 확정하지 않음 | HTTP 공개 표기 openresty. CDN·원본 서버 UNKNOWN |
| `customer.json` | CMS·프런트엔드·백엔드 UNKNOWN, Server 및 CF-Ray | 기술 미확인. Cloudflare 마커는 별도 표시 | HTTP 공개 표기 cloudflare, CDN Cloudflare. 원본 서버 UNKNOWN |
| `imweb_gilnmi.json` | `cdn.imweb.me` 이미지 5개, 신뢰도 0.55 | Imweb 후보 · 미확정. 외부 이미지 사용만으로 아임웹 운영을 증명하지 않음 | HTTP 공개 표기 CloudFront. 기존 CDN UNKNOWN 유지. 원본 서버 UNKNOWN |
| `nextjs_official.json` | `/_next/static/` 빌드 자원 10개, 신뢰도 0.80 | Next.js 빌드 자원 확인. React·Node.js·자체 개발 여부 추정 금지 | HTTP 공개 표기 Vercel. CDN·원본 서버 UNKNOWN |
| `unknown_example.json` | CMS·프런트엔드·백엔드 UNKNOWN, Server 및 CF-Ray | 기술 미확인. customer.json과 같은 대상이지만 별도 분석 기록으로 보존 | HTTP 공개 표기 cloudflare, CDN Cloudflare. 원본 서버 UNKNOWN |
| `wordpress_nasa.json` | generator `WordPress 7.0.7` 1개 및 wp-content 자원 9개, 신뢰도 0.95 | WordPress 명시 표기 확인. 버전은 원문 관찰값이며 실제 운영 버전 확인을 뜻하지 않음 | HTTP 공개 표기 nginx. CDN·원본 서버 UNKNOWN |

총 7건: 단서 있음 4건, 기술 미확인 2건, 보안 차단 1건, 분석 오류 0건, JSON 입력 오류 0건입니다. 서버·CDN 근거를 포함한 전체 저장 근거는 42개입니다. 보안 차단과 미확인은 원인이 다르므로 통합하지 않습니다.

표기 확인은 실제 플랫폼 확정과 다릅니다. 아임웹·카페24의 확정 규칙은 현재 없으며, 임의의 generator 이름·높은 신뢰도·호스팅 도메인·외부 자원 수로 새 확정 판정을 만들지 않았습니다. CloudFront·Vercel 등의 HTTP Server 표기 역시 CDN 또는 원본 서버를 새로 탐지하는 규칙으로 사용하지 않았습니다.

보고서의 ‘전체 근거’는 저장된 JSON에 존재하는 근거만 의미합니다. 최초 탐지기의 기술당 최대 10개 저장 제한은 그대로 유지합니다. HTML 출력과 터미널 요약에만 마스킹을 적용하며, 버전 원문을 포함한 입력 JSON은 변경하지 않습니다.
