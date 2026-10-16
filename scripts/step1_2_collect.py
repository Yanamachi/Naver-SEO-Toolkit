"""One-off, fixed five-site experiment. Not an Environment Detector adapter.

Run explicitly: python scripts/step1_2_collect.py
Never imported by the product CLI. No path/port enumeration or follow-up probes.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from environment_detector import cli  # noqa: E402
from environment_detector.fetch import fetch_page  # noqa: E402
from environment_detector.safety import resolve_destination  # noqa: E402

TARGETS = (
    ("wordpress_nasa", "https://www.nasa.gov/"),
    ("imweb_gilnmi", "https://gilnmi.imweb.me/"),
    ("cafe24_demo", "https://ecudemo159670.cafe24.com/"),
    ("nextjs_official", "https://nextjs.org/"),
    ("unknown_example", "https://example.com/"),
)
OUT = ROOT / "results" / "step1.2"
BINARY = ROOT / "tools" / "projectdiscovery-httpx" / "v1.12.0" / "pd-httpx.exe"
EXPECTED_BINARY_SHA256 = "95129b2771ad64e675a436279bdfb72cbf00000ebab482f045d021fffff6fbeb"
AGENT = "EnvironmentDetector/0.1 (read-only)"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pd_command(url, addresses, config):
    return [str(BINARY), "-u", url, "-tech-detect", "-server", "-cdn", "-status-code",
            "-response-time", "-probe", "-json", "-include-response", "-include-response-header",
            "-threads", "1", "-rate-limit", "1", "-delay", "1s", "-retries", "0",
            "-timeout", "10", "-no-fallback-scheme", "-x", "GET", "-protocol", "http11",
            "-exclude", "private-ips", "-deny", "168.63.129.16", "-allow", ",".join(addresses),
            "-response-size-to-read", "2097152", "-response-size-to-save", "2097152",
            "-random-agent=false", "-H", "User-Agent: " + AGENT,
            "-H", "Accept: text/html,application/xhtml+xml", "-H", "Accept-Encoding: identity",
            "-config", str(config), "-auth=false", "-disable-update-check", "-no-stdin", "-silent", "-no-color"]


def main():
    if not BINARY.is_file():
        raise SystemExit("Install verified ProjectDiscovery v1.12.0 as tools/projectdiscovery-httpx/v1.12.0/pd-httpx.exe first.")
    if hashlib.sha256(BINARY.read_bytes()).hexdigest() != EXPECTED_BINARY_SHA256:
        raise SystemExit("Unexpected binary: this experiment requires the verified Windows amd64 v1.12.0 executable.")
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "measurements.json").exists():
        raise SystemExit("Existing experiment preserved. Archive results/step1.2 before a deliberate rerun.")
    config = OUT / "empty-config.yaml"
    config.write_text("{}\n", encoding="utf-8")
    own_dir = OUT / "detector"
    pd_dir = OUT / "projectdiscovery"
    own_dir.mkdir(exist_ok=True)
    pd_dir.mkdir(exist_ok=True)
    env = {key: value for key, value in os.environ.items()
           if "proxy" not in key.lower() and not key.upper().startswith(("PDCP_", "HTTPX_"))}
    env["DISABLE_TELEMETRY"] = "true"
    measurements = {"started_at": datetime.now(timezone.utc).isoformat(), "pd_version": "v1.12.0",
                    "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(), "targets": []}
    jsonl = []
    original_fetch = cli.fetch_page
    try:
        for name, url in TARGETS:
            # Reject mixed/private DNS answers before either engine is executed.
            destination = resolve_destination(url)
            page_capture = {}

            def capture(value):
                page = fetch_page(value)
                page_capture.update(url=page.url, headers=dict(page.headers), html=page.html,
                                    status_code=page.status_code)
                return page

            cli.fetch_page = capture
            start = time.perf_counter()
            own = cli.run(url)
            own_elapsed = time.perf_counter() - start
            dump(own_dir / f"{name}.json", own)
            if page_capture:
                dump(own_dir / f"{name}.response.json", page_capture)
            time.sleep(1)
            command = pd_command(url, destination.addresses, config)
            start = time.perf_counter()
            try:
                process = subprocess.run(command, capture_output=True, timeout=35, env=env)
                stdout = process.stdout.decode("utf-8", errors="replace")
                stderr = process.stderr.decode("utf-8", errors="replace")
                returncode = process.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
                stderr = "PROCESS_TIMEOUT\n" + (exc.stderr or b"").decode("utf-8", errors="replace")
                returncode = None
            pd_elapsed = time.perf_counter() - start
            (pd_dir / f"{name}.jsonl").write_text(stdout, encoding="utf-8")
            (pd_dir / f"{name}.stderr.txt").write_text(stderr, encoding="utf-8")
            rows = []
            for line in stdout.splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
                    jsonl.append(json.dumps(row, ensure_ascii=False))
            measurement = {"name": name, "url": url, "preflight_addresses": destination.addresses,
                           "detector_elapsed_seconds": round(own_elapsed, 4), "detector_status": own["status"],
                           "pd_elapsed_seconds": round(pd_elapsed, 4), "pd_returncode": returncode,
                           "pd_records": len(rows), "pd_command": command}
            measurements["targets"].append(measurement)
            dump(OUT / "measurements.partial.json", measurements)
            print(f"{name}: detector={own['status']} {own_elapsed:.3f}s; PD records={len(rows)} exit={returncode} {pd_elapsed:.3f}s", flush=True)
            time.sleep(1)
    finally:
        cli.fetch_page = original_fetch
    measurements["finished_at"] = datetime.now(timezone.utc).isoformat()
    dump(OUT / "measurements.json", measurements)
    (pd_dir / "results.jsonl").write_text("\n".join(jsonl) + ("\n" if jsonl else ""), encoding="utf-8")


if __name__ == "__main__":
    main()
