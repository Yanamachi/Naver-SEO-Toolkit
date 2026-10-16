# 탐지 규칙 근거

공식 문서에서 확인한 공개 단서만 사용합니다. 문서는 규칙 구현 시 확인했으며 실행 중 외부 문서 조회는 하지 않습니다. 각 JSON 근거에도 해당 링크를 포함합니다.

| 규칙 ID | 공식 자료 | 적용 및 한계 |
| --- | --- | --- |
| `wordpress_generator` | [WordPress wp_generator](https://developer.wordpress.org/reference/functions/wp_generator/) | generator 표기를 확인하며 실제 운영 서버나 PHP를 추정하지 않음 |
| `wordpress_assets` | [WordPress 파일 구조](https://learn.wordpress.org/lesson/understand-where-your-files-live/) | wp-content의 테마/플러그인/업로드 자원; 정적 복사본 가능 |
| `imweb_assets` | [아임웹 이미지 호스트 안내](https://imweb.me/qna?mode=faq&q=27524) | cdn.imweb.me 자원 소속만 확인; 다른 사이트에서 재사용 가능 |
| `cafe24_assets` | [카페24 공식 스마트디자인 상품 상세 예제](https://sdsupport.cafe24.com/module/product/detail.html) | img.echosting.cafe24.com 템플릿 이미지; 카페24 플랫폼 확정 불가 |
| `next_assets` | [Next.js 7 빌드 자원 경로](https://nextjs.org/blog/next-7) | /_next/static/ 자원; 서버 런타임 추정 금지 |
| `next_header` | [Next.js poweredByHeader](https://nextjs.org/docs/pages/api-reference/config/next-config-js/poweredByHeader) | X-Powered-By 표기; 설정으로 제거 가능 |
| `express_header` | [Express application API](https://expressjs.com/en/4x/api/application/) | X-Powered-By 표기만 사용 |
| `php_header` | [PHP expose_php](https://www.php.net/manual/en/ini.core.php) | X-Powered-By의 PHP 표기만 사용 |
| `server_header` | [RFC 9110 Server](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.4) | 광고된 응답 서버 값; 원본 서버와 다를 수 있음 |
| `cloudflare_ray` | [Cloudflare 응답 CF-Ray](https://developers.cloudflare.com/speed/troubleshooting/slow-website/) | Cloudflare를 거친 응답 단서; 원본 기술 미상 |

IP 고정 및 TLS SNI는 [HTTPX의 공식 sni_hostname 확장](https://www.python-httpx.org/advanced/extensions/#sni_hostname)을 사용합니다. 소켓 연결 URL은 검사한 IP이고, Host 및 인증서 검증 대상은 고객이 입력한 호스트입니다.
