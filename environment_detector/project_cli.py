"""Additive project commands; existing scan/report commands remain unchanged."""

import argparse
import json
from pathlib import Path
import sys

from .intake import IntakeError, private_copy
from .projects import create_project, review_project


def main(argv):
    parser = argparse.ArgumentParser(prog="environment_detector project", description="고객 의뢰 접수 및 읽기 전용 사전 견적 검토")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="의뢰 JSON으로 프로젝트 생성")
    create.add_argument("intake", type=Path)
    create.add_argument("--projects-dir", type=Path, default=Path("customer-data/projects"))
    create.add_argument("--job-id")
    source = create.add_mutually_exclusive_group()
    source.add_argument("--environment", type=Path, help="동일 URL의 기존 탐지 JSON 재사용")
    source.add_argument("--reuse-dir", type=Path, help="동일 URL의 최신 성공 결과 검색 (기본 results, 하위 폴더 제외)")
    source.add_argument("--analyze", action="store_true", help="의뢰서의 명시적 분석 동의가 있을 때만 새 분석")
    create.add_argument("--review-notes", type=Path, help="고객 진술과 별도인 담당자 검토 기록")
    review = sub.add_parser("review", help="기존 프로젝트의 오프라인 재검토·HTML 재생성")
    review.add_argument("folder", type=Path)
    review.add_argument("--review-notes", type=Path)
    audit = sub.add_parser("audit", help="동의한 프로젝트의 공개 페이지 SEO 읽기 전용 분석")
    audit.add_argument("folder", type=Path)
    audit.add_argument("--max-pages", type=int, default=20)
    audit.add_argument("--crawl", action="store_true", help="동일 출처 공개 내부 링크의 제한적 탐색을 별도 승인")
    audit.add_argument("--check-sitemaps", action="store_true", help="robots 선언 사이트맵 최대 3개 문서 검사 승인")
    audit.add_argument("--interval", type=float, default=1.0)
    audit.add_argument("--timeout", type=float, default=10.0)
    audit.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024)
    audit.add_argument("--indexing-goal", choices=("unknown", "index", "noindex"), default="unknown", help="고객이 명시한 대상 페이지 색인 의도; 기본 미확인")
    audit.add_argument("--report-only", action="store_true", help="기존 SEO JSON에서 HTML만 재생성; 네트워크 요청 없음")
    dashboard = sub.add_parser("dashboard", help="기존 프로젝트 JSON에서 오프라인 통합 작업 화면 생성")
    dashboard.add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "dashboard":
            from .workbench import save_dashboard
            output, model = save_dashboard(args.folder)
            print(json.dumps(private_copy({"job_id": model["job_id"], "dashboard_html": str(output),
                "synthetic_data_present": model["synthetic"],
                "customer_stages": {key: value[0] for key, value in model["states"].items()}}), ensure_ascii=False, indent=2))
            return 0
        if args.command == "audit":
            from .seo_audit import AuditOptions, audit_project, regenerate_report
            options = AuditOptions(args.max_pages, args.crawl, args.check_sitemaps, args.interval,
                                   args.timeout, args.max_bytes, args.indexing_goal)
            result = regenerate_report(args.folder) if args.report_only else audit_project(args.folder, options=options)
            print(json.dumps(private_copy({"job_id": result["job_id"], "status": result["status"], **result["summary"],
                "result_json": str((args.folder / "seo-audit.json").resolve()),
                "report_html": str((args.folder / "seo-report.html").resolve())}), ensure_ascii=False, indent=2))
            return 1 if result["status"] == "BLOCKED" else 0
        if args.command == "create":
            folder, project, result = create_project(args.intake, projects_dir=args.projects_dir, job_id=args.job_id,
                environment_path=args.environment, reuse_dir=args.reuse_dir, analyze=args.analyze, notes_path=args.review_notes)
        else:
            folder, project, result = review_project(args.folder, notes_path=args.review_notes)
    except IntakeError as exc:
        print("프로젝트 처리에 실패했습니다. " + private_copy(str(exc)), file=sys.stderr)
        return 1
    except (OSError, ValueError, RecursionError):
        print("프로젝트 처리에 실패했습니다. 입력 형식·동일 URL·작업 ID 중복·출력 경로 권한을 확인하세요. 기존 파일은 임의로 덮어쓰지 않습니다.", file=sys.stderr)
        return 1
    print(json.dumps(private_copy({"job_id": project["job_id"], "decision": result["decision"],
                                  "questions_count": len(result["questions"]), "project_dir": str(folder.resolve()),
                                  "report_html": str((folder / "report.html").resolve())}), ensure_ascii=False, indent=2))
    return 0
