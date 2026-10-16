"""Render the fixed STEP 1.2 experiment offline; human review, not a new detector."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from environment_detector.redact import redact  # noqa: E402
from environment_detector.report import STYLE, h  # noqa: E402

# Human judgments from the saved five-site responses and the pinned upstream rules.
# Resource/markup evidence is never promoted to confirmed server-side execution.
REVIEWS = {
    "wordpress_nasa": {
        "cms": "양쪽 WordPress 명시 표기. generator 7.0.7은 관찰 문자열이며 운영 버전 검증 아님.",
        "missed": "Gravity Forms 자원, WordPress Block Editor 마크업, Google Tag Manager 코드. jQuery는 관련 자원 후보이며 실행·기본 라이브러리는 미검증.",
        "evidence": ["meta generator: WordPress 7.0.7", "/wp-content/plugins/gravityforms/js/gravityforms.min.js?ver=3.1.2", "div class에 wp-block-*", "iframe src=https://www.googletagmanager.com/ns.html"],
        "limits": "PHP·MySQL은 WordPress 지문의 implies 결과. X-Powered-By/DB 직접 단서가 없어 정답·누락 목록에서 제외. WP 부가 출력의 popup-maker, wp-parsely, accessibility-checker도 자원/마크업 수준.",
    },
    "imweb_gilnmi": {
        "cms": "자체 Imweb 후보. PD도 Imweb을 출력하지만 vendor-cdn 자원 규칙이므로 플랫폼 확정으로 승격하지 않음.",
        "missed": "Bootstrap, Chosen, Lodash, Modernizr, Moment.js, OWL Carousel, Slick, jQuery, jQuery UI 자원 및 Kakao SDK·Naver Analytics 자원. CloudFront 응답/엣지 단서.",
        "evidence": ["script src=https://vendor-cdn.imweb.me/js/bootstrap.min.js", "script src=https://vendor-cdn.imweb.me/js/jquery.chosen.js", "script src=https://vendor-cdn.imweb.me/js/lodash.min.js", "script src=https://vendor-cdn.imweb.me/js/modernizr.custom.js", "script src=https://vendor-cdn.imweb.me/js/moment.min.js", "script src=https://vendor-cdn.imweb.me/js/owl.carousel2.js", "script src=https://vendor-cdn.imweb.me/js/slick.min.js", "script src=https://vendor-cdn.imweb.me/js/jquery.js", "script src=https://vendor-cdn.imweb.me/js/jquery-ui.design.js", "script src=https://developers.kakao.com/sdk/js/kakao.min.js", "script src=//wcs.naver.net/wcslog.js", "Via: ...cloudfront.net (CloudFront); X-Amz-Cf-Id 응답 헤더; 연결 IP 13.225.117.7"],
        "limits": "자체는 Server: CloudFront를 이미 기록하나 CDN 범주는 UNKNOWN. PD cdn_name=cloudfront는 연결 IP의 CDN 분류이며 헤더와도 부합. Amazon Web Services는 CloudFront의 implies: AWS 엣지 문맥만 인정하고 원본 호스팅은 UNKNOWN.",
    },
    "cafe24_demo": {
        "cms": "자체 Cafe24 후보. PD 목록에는 Cafe24가 없음. img.echosting.cafe24.com 자원이 있으나 실제 플랫폼 확정 불가.",
        "missed": "jQuery 자원(파일명 1.11.0), OWL Carousel 자원, cdnjs 외부 자원, YouTube iframe. Lightbox 계열 자원은 있으나 제품명 Lightbox2 여부는 미검증.",
        "evidence": ["script src=/roma/js/jquery-1.11.0.min.js", "script src=/roma/romaowl/owl.carousel.100.js", "script src=https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.7/gsap.min.js", "script src=/roma/js/simple-lightbox.jquery.min.js", "주석 밖 iframe src=https://www.youtube.com/embed/oQDLAoPs-as", "Server: openresty; CF-Ray 없음; PD cdn_name 없음"],
        "limits": "Cloudflare는 cdnjs → Cloudflare implies 결과: 외부 자원 제공자이며 대상 사이트 CDN으로 해석하면 오분류. Nginx도 OpenResty → Nginx implies로 원본 서버의 독립 확인 아님. Lightbox의 넓은 정규식은 simple-lightbox 파일에도 매칭하므로 정확한 제품 확인으로 채택하지 않음.",
    },
    "nextjs_official": {
        "cms": "양쪽 CMS 미식별. 자체는 /_next/static/로 Next.js 빌드 자원 확인. PD는 Next.js를 출력하지 않음.",
        "missed": "React 계열 마크업 후보(data-react-aria-pressable). React 런타임을 확인한 정답으로 계산하지 않음.",
        "evidence": ["script src=/_next/static/immutable/chunks/0q93co9tqv6p5.js", "button/a 속성 data-react-aria-pressable=true", "Alt-Svc: h3=\":443\"; Server: Vercel"],
        "limits": "p5.js는 해시 청크명 끝 p5.js에 비고정 정규식이 매칭한 오탐 후보. p5 라이브러리 사용을 증명하지 않아 정답에서 제외. HTTP/3은 Alt-Svc 광고이며 이번 GET의 협상 프로토콜(HTTP/1.1)과 다름. Vercel 공개 표기는 양쪽 동일, 원본 서버는 UNKNOWN.",
    },
    "unknown_example": {
        "cms": "자체 CMS·프런트엔드·백엔드 UNKNOWN. PD도 해당 기술 없음. 사이트 접근 실패가 아닌 기술 미식별.",
        "missed": "추가 CMS/프레임워크 단서 없음. HTTP/3 서비스 광고만 추가(현재 프로토콜 검증 아님).",
        "evidence": ["Server: cloudflare; CF-Ray; PD cdn_name=cloudflare, cdn_type=waf", "Alt-Svc: h3=\":443\""],
        "limits": "Cloudflare 응답/엣지는 양쪽 부합. CMS 목록 부재를 CMS 없음이나 자체 개발로 해석하지 않음.",
    },
}
COMMON = [
    "판정 OPTIONAL: 독립적인 보조 점검·라이브러리 목록에는 가치가 있지만 현재 핵심 엔진에 통합할 필요는 입증되지 않았습니다. 이번 단계에서는 결합하지 않습니다.",
    "추가 자원·헤더 단서의 폭은 넓습니다. 그러나 Cafe24와 Next.js 누락, implies 연쇄 추정, 해시 파일명 충돌 때문에 외부 tech 목록을 사실로 자동 수용할 수 없습니다.",
    "HSTS는 NASA·Cafe24·Next.js의 Strict-Transport-Security 헤더에서 확인합니다. HTTP/3은 Next.js·example.com의 Alt-Svc 광고입니다. 이 둘은 CMS/프레임워크 누락과 별도인 헤더 기능 범위입니다.",
    "정답은 공개 응답에서 확인한 표기·자원·마크업 수준으로 제한합니다. 서버 소스·DB·실제 JS 실행을 확인하지 않았고, 독립적인 전체 정답표도 없어 정확도 비율을 산출하지 않습니다. 두 도구의 신뢰도 수치는 비교하지 않습니다.",
    "HTTP 접근 성공, CMS/프레임워크 미식별, CDN 미식별은 각각 다릅니다. PD 필드 부재는 UNKNOWN으로 해석하며 기술 부재로 판단하지 않습니다. 접근 상태는 비교표에 별도로 표시합니다.",
    "자체 JSON은 규칙·관찰값·위치·공식 자료를 제공합니다. PD 기본 tech 배열은 매칭 위치·implies 여부를 설명하지 않습니다. 저장된 body/header와 고정 버전 지문을 수동 대조해 보완했습니다.",
    "설정 범위는 각 도구당 5개 HTTPS 루트 GET, 재시도 없음입니다. 자체 결과 리다이렉트 이력은 모두 비어 있고 PD 리다이렉트·HTTP 대체를 비활성화했습니다. PD request 필드도 GET / HTTP/1.1 5건입니다. 별도 패킷 캡처는 하지 않았습니다.",
    "단일 순차 실행이며 같은 UA·Accept·identity 인코딩을 요청했습니다. 응답은 동적이고 별도 시각에 받았으므로 바이트 동일성은 가정하지 않습니다. PD 실행시간에는 프로세스 시작·지문 초기화·명시적 1초 pacing이 포함돼 순수 엔진 속도 비교가 아닙니다.",
    "TLS 정책도 다릅니다. 자체는 인증서를 검증하지만 PD v1.12.0이 사용하는 fastdialer v0.5.19의 DefaultTLSConfig는 InsecureSkipVerify=true입니다. 이번 성공 사례로 인증서 유효성까지 동등하게 검증했다고 해석하지 않습니다.",
    "설치·분석·보고서 모두 실험 스크립트에 분리했습니다. 기존 CLI/JSON/탐지 규칙/HTML 보고서는 유지합니다. 재수집은 자동 실행하지 않으며 HTML 재생성은 저장 파일만 읽습니다.",
]
SOURCES = [
    ("Windows 공식 배포 / v1.12.0", "https://github.com/projectdiscovery/httpx/releases/tag/v1.12.0"),
    ("공식 설치 문서", "https://docs.projectdiscovery.io/opensource/httpx/install"),
    ("옵션 및 기술 탐지 데이터셋", "https://docs.projectdiscovery.io/opensource/httpx/usage"),
    ("MIT 라이선스", "https://github.com/projectdiscovery/httpx/blob/v1.12.0/LICENSE.md"),
    ("고정 지문 규칙: wappalyzergo v0.2.96", "https://github.com/projectdiscovery/wappalyzergo/blob/v0.2.96/fingerprints_data.json"),
    ("implies 처리 구현", "https://github.com/projectdiscovery/wappalyzergo/blob/v0.2.96/fingerprints.go"),
    ("응답 기반 탐지 및 CDN 분류 호출", "https://github.com/projectdiscovery/httpx/blob/v1.12.0/runner/runner.go"),
    ("fastdialer 기본 TLS 설정", "https://github.com/projectdiscovery/fastdialer/blob/v0.5.19/fastdialer/default_config.go"),
]


def access_state(result, external=False):
    """Separate missing output/transport/HTTP errors from absent technology labels."""
    if result is None:
        return "출력 없음 · 접근 여부 미확인"
    if external:
        if result.get("failed") or result.get("error"):
            return "접근 실패 · 기술 평가 제외"
        status = result.get("status_code")
    else:
        if result.get("status") != "ok":
            return "분석 실패 · 기술 평가 제외: " + ", ".join(e.get("code", "UNKNOWN") for e in result.get("errors", []))
        status = (result.get("http") or {}).get("status_code")
    if not isinstance(status, int):
        return "HTTP 상태 미확인 · 기술 평가 제외"
    if not 200 <= status < 300:
        return f"HTTP {status} · 대상 콘텐츠의 기술 평가 제외"
    return f"HTTP {status} · 접근 성공"


def load_comparison(folder):
    measurements = json.loads((folder / "measurements.json").read_text(encoding="utf-8"))
    external = [json.loads(line) for line in (folder / "projectdiscovery" / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for target in measurements["targets"]:
        own = json.loads((folder / "detector" / (target["name"] + ".json")).read_text(encoding="utf-8"))
        matches = [r for r in external if r.get("input", r.get("url")) == target["url"]]
        if len(matches) > 1:
            raise ValueError("Duplicate external records; review before comparing.")
        pd = matches[0] if matches else None
        comparable = access_state(own).endswith("접근 성공") and access_state(pd, True).endswith("접근 성공")
        rows.append({"name": target["name"], "url": target["url"],
                     "own_access": access_state(own), "pd_access": access_state(pd, True),
                     "own_technologies": own["technologies"], "pd_tech": (pd or {}).get("tech", []),
                     "pd_server": (pd or {}).get("webserver") or "UNKNOWN",
                     "pd_cdn": (pd or {}).get("cdn_name") or "UNKNOWN",
                     "pd_cdn_type": (pd or {}).get("cdn_type") or "UNKNOWN",
                     "own_elapsed": target["detector_elapsed_seconds"], "pd_elapsed": target["pd_elapsed_seconds"],
                     "pd_response_time": (pd or {}).get("time", "UNKNOWN"),
                     "comparable": comparable,
                     "review": REVIEWS[target["name"]] if comparable else {"cms": "접근/분석 실패로 식별 평가 보류", "missed": "판정 보류", "evidence": [], "limits": "성공한 동일 대상 콘텐츠 없이 정확성 평가하지 않습니다."}})
    decision = "OPTIONAL" if len(rows) == 5 and all(row["comparable"] for row in rows) else "판정 보류"
    conclusions = list(COMMON)
    if decision != "OPTIONAL":
        conclusions[0] = "판정 보류: 비교 대상 콘텐츠나 출력이 누락되어 이번 입력만으로 도입 판단하지 않습니다. 아래 기술별 기존 검토도 미완료 대상을 평가하는 근거로 사용하지 않습니다."
    return redact({"decision": decision, "pd_version": measurements["pd_version"],
                   "started_at": measurements["started_at"], "finished_at": measurements["finished_at"],
                   "rows": rows, "conclusions": conclusions, "sources": SOURCES})


def technology_text(technologies):
    return " | ".join(category + ": " + ", ".join(item["name"] for item in technologies[category])
                      for category in ("cms", "frontend", "backend", "server", "cdn"))


def render_comparison(data):
    table_rows = []
    sections = []
    for row in data["rows"]:
        values = [row["url"], row["own_access"] + " / " + row["pd_access"], technology_text(row["own_technologies"]),
                  ", ".join(row["pd_tech"]) or "UNKNOWN (목록 없음)", row["pd_server"] + " / " + row["pd_cdn"] + " (" + row["pd_cdn_type"] + ")",
                  f"자체 {row['own_elapsed']:.3f}s / PD {row['pd_elapsed']:.3f}s (응답 {row['pd_response_time']})"]
        table_rows.append("<tr>" + "".join("<td>" + h(value) + "</td>" for value in values) + "</tr>")
        review = row["review"]
        sections.append('<section class="card"><h2>' + h(row["url"]) + '</h2>' +
                        "".join("<h3>" + label + "</h3><p>" + h(review[key]) + "</p>" for label, key in
                                (("CMS / 프레임워크 판단", "cms"), ("자체 미지원 추가 단서 (운영 확정 아님)", "missed"), ("외부 도구의 추정·오탐·한계", "limits"))) +
                        '<details><summary>검토한 공개 근거 펼쳐보기</summary><ul>' + "".join("<li>" + h(e) + "</li>" for e in review["evidence"]) + '</ul></details></section>')
    conclusions = "".join("<li>" + h(line) + "</li>" for line in data["conclusions"])
    sources = "".join("<li>" + h(label) + ": " + h(url) + "</li>" for label, url in data["sources"])
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>STEP 1.2 · 탐지 엔진 비교</title><style>''' + STYLE + '''td{min-width:180px}main{max-width:1500px}</style></head><body><main><header><div class="eyebrow">ENVIRONMENT DETECTOR · STEP 1.2</div><h1>외부 탐지 엔진 도입 검증</h1><p>ProjectDiscovery httpx ''' + h(data["pd_version"]) + ''' vs 자체 Detector · 공개 사이트 5곳 · 단일 제한 실행</p></header><aside class="notice"><strong>판정: ''' + h(data["decision"]) + '''</strong><p>핵심 엔진 통합은 진행하지 않습니다. 신뢰도 수치와 추정 기술 개수로 우열을 계산하지 않습니다.</p><p>실험 시각: ''' + h(data["started_at"]) + " ~ " + h(data["finished_at"]) + '''. 이 HTML은 저장 결과만 읽어 생성합니다.</p></aside><h2>도구별 결과 비교</h2><div class="scroll"><table><thead><tr><th>대상</th><th>자체 / PD 접근 상태</th><th>자체 기술 범주</th><th>PD tech 원문 목록</th><th>PD HTTP 서버 / CDN</th><th>전체 경과 시간</th></tr></thead><tbody>''' + "".join(table_rows) + '</tbody></table></div><section class="card"><h2>도입 판단과 검증 범위</h2><ul>' + conclusions + '</ul></section>' + "".join(sections) + '<details class="card"><summary>공식 자료 (실행 가능한 링크가 아닌 텍스트)</summary><ul>' + sources + '</ul></details><footer><p>원본 서버·DB·호스팅·실행 여부는 미확인입니다. 확인된 자원 이름과 제품의 실제 사용을 구분하세요.</p></footer></main></body></html>'


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline renderer for the fixed STEP 1.2 experiment")
    parser.add_argument("--folder", type=Path, default=ROOT / "results" / "step1.2")
    args = parser.parse_args(argv)
    data = load_comparison(args.folder)
    (args.folder / "comparison.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    output = args.folder / "comparison.html"
    output.write_text(render_comparison(data), encoding="utf-8")
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
