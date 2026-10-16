"""JSON CLI: stdout is always the result; diagnostics go to stderr."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .detect import CATEGORIES, analyze, unknown
from .fetch import fetch_page
from .safety import DetectorError


def run(url: str) -> dict:
    result = {
        "schema_version": "1.0", "status": "error",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "request_url": url, "final_url": None, "http": None,
        "technologies": {category: [unknown()] for category in CATEGORIES},
        "development_model": unknown(), "errors": [],
    }
    try:
        page = fetch_page(url)
        result.update(analyze(page.headers, page.html, page.url))
        result.update(status="ok", final_url=page.url, http={
            "status_code": page.status_code, "size_bytes": page.size_bytes,
            "redirects": page.redirects,
            # Avoid persisting cookies and arbitrary headers with customer secrets.
            "headers": {key: page.headers[key] for key in
                        ("content-type", "server", "x-powered-by", "cf-ray") if key in page.headers},
        })
    except DetectorError as exc:
        result["errors"].append({"code": exc.code, "message": str(exc)})
    return result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "project":
        from .project_cli import main as project_main
        return project_main(argv[1:])
    if argv and argv[0] == "report":
        return report_main(argv[1:])
    parser = argparse.ArgumentParser(description="Detect public website technology clues (read-only).",
                                     epilog="Offline HTML report: python -m environment_detector report ./results -o ./results/report.html")
    parser.add_argument("url", help="Absolute public HTTP(S) URL")
    parser.add_argument("-o", "--output", type=Path, help="Save JSON (default: results/environment.json)",
                        default=Path("results/environment.json"))
    parser.add_argument("--summary", action="store_true", help="Print a masked terminal summary to stderr; stdout remains JSON")
    args = parser.parse_args(argv)
    result = run(args.url)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    except (OSError, ValueError):
        result["status"] = "error"
        result["errors"].append({"code": "OUTPUT_ERROR", "message": "Could not save JSON output."})
        payload = json.dumps(result, ensure_ascii=False, indent=2)
        print("Could not save JSON output.", file=sys.stderr)
    print(payload)
    if args.summary:
        from .redact import redact
        from .report import Entry, result_state, terminal_summary
        print(terminal_summary([Entry("current result", redact(result), result_state(result))]), file=sys.stderr)
    return 0 if result["status"] == "ok" else 1


def report_main(argv: list[str]) -> int:
    from .report import load_entries, save_report, terminal_summary
    from .redact import mask_text

    parser = argparse.ArgumentParser(prog="environment_detector report", description="Offline HTML report from existing JSON; no site requests.")
    parser.add_argument("source", type=Path, help="JSON file or directory (non-recursive)")
    parser.add_argument("-o", "--output", type=Path, help="Output .html (default: report.html beside input)")
    args = parser.parse_args(argv)
    output = args.output or ((args.source if args.source.is_dir() else args.source.parent) / "report.html")
    try:
        entries = load_entries(args.source)
        save_report(output, entries)
    except (OSError, ValueError):
        print("보고서를 생성하지 못했습니다. 입력 JSON 경로·출력 .html 경로·파일 권한을 확인하세요.", file=sys.stderr)
        return 1
    print(terminal_summary(entries))
    print("HTML: " + mask_text(str(output.resolve())))
    return 1 if any(entry.state == "input_error" for entry in entries) else 0
