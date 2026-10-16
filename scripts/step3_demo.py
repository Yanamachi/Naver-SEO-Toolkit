"""Reproduce one synthetic project/audit using ONLY fixed mock HTTP responses."""

import argparse
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from environment_detector.projects import create_project, write_json  # noqa: E402
from environment_detector.seo_audit import AuditOptions, audit_project  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="가상 병원 SEO 분석 재현 · 실제 네트워크 요청 없음")
    parser.add_argument("--job-id", default="JOB-DEMO-SEO")
    args = parser.parse_args()
    site = "https://hospital.example.com/"
    source = ROOT / "results/step3/demo-input"
    source.mkdir(parents=True, exist_ok=True)
    form = json.loads((ROOT / "templates/examples/hospital-intake.json").read_text(encoding="utf-8-sig"))
    form.update(company_name="가상 SEO 병원 · 테스트 전용", site_url=site, requested_services=["seo"],
                target_page_urls=[site, site + "doctors"], public_analysis_consent=True,
                additional_requests="실제 동의가 아닌 모의 테스트 입력입니다. 운영 사이트 요청 금지.")
    write_json(source / "intake.json", form)
    folder, project, _ = create_project(source / "intake.json", projects_dir=ROOT / "customer-data/projects", job_id=args.job_id,
                                  environment_path=ROOT / "templates/examples/hospital-environment.json")
    project["data_origin"] = "SYNTHETIC_TEST_FIXTURE"
    write_json(folder / "project.json", project)
    normal = (ROOT / "tests/fixtures/seo/normal.html").read_text(encoding="utf-8")
    doctor = normal.replace("가상 병원 진료 안내", "가상 의료진 소개").replace('href="' + site + '"', 'href="' + site + 'doctors"')
    doctor = doctor.replace('<meta name="description" content="가상 병원 진료 내용과 진료 시간 안내">', '')
    doctor = doctor.replace('<img src="/doctor.jpg" alt="가상 의료진 설명">', '<img src="/doctor.jpg">')
    sitemap = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + site + '</loc></url><url><loc>' + site + 'doctors</loc></url></urlset>'
    routes = {"/robots.txt": ("User-agent: *\nAllow: /\nUser-agent: Yeti\nAllow: /\nSitemap: " + site + "sitemap.xml", "text/plain"),
              "/": (normal, "text/html; charset=utf-8"), "/doctors": (doctor, "text/html; charset=utf-8"),
              "/sitemap.xml": (sitemap, "application/xml")}
    def handler(request):
        assert request.method == "GET" and request.headers["host"] == "hospital.example.com"
        assert request.url.host == "93.184.216.34"
        body, content_type = routes[request.url.path]
        return httpx.Response(200, headers={"content-type": content_type}, stream=httpx.ByteStream(body.encode()))
    def forbidden(*args, **kwargs):
        raise AssertionError("실제 네트워크 요청은 금지됩니다.")
    with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), patch.object(socket, "create_connection", side_effect=forbidden):
        result = audit_project(folder, options=AuditOptions(check_sitemaps=True, indexing_goal="index"),
                               transport=httpx.MockTransport(handler), sleeper=lambda _: None)
    print(json.dumps({"data_origin": result["data_origin"], "summary": result["summary"],
                      "result_json": str(folder / "seo-audit.json"), "report_html": str(folder / "seo-report.html")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
