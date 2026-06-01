#!/usr/bin/env python3
"""
run_all.py
Cross-platform master orchestrator.

Runs all available coverage pipelines in PARALLEL using ThreadPoolExecutor
(one thread per tool), streams interleaved output prefixed by tool name,
then generates the landing page when all pipelines complete.

Available pipelines:
  gcov     — GCC + gcovr          (macOS / Linux / Windows)
  llvm     — Clang + llvm-cov     (macOS / Linux / Windows)
  opencpp  — MSVC + OpenCppCoverage (Windows only — silently skipped elsewhere)
  microsoft — MSVC + Microsoft Code Coverage (Windows only — silently skipped elsewhere)

Usage:
  python scripts/run_all.py
  python scripts/run_all.py --non-interactive --install   # CI
  python scripts/run_all.py --skip-prereqs                # skip check
  python scripts/run_all.py --tools gcov llvm             # subset of tools
"""

from __future__ import annotations

import argparse
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT   = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()

# ── Console helpers ───────────────────────────────────────────────────────────

TOOL_COLOR = {
    "gcov":    "32",   # green
    "llvm":    "35",   # magenta
    "opencpp": "33",   # yellow
    "microsoft": "34", # blue
}

def _c(code: str, text: str) -> str:
    if SYSTEM == "Windows" and not os.environ.get("WT_SESSION"):
        return text
    return f"\033[{code}m{text}\033[0m"

def _tool_prefix(tool: str) -> str:
    color = TOOL_COLOR.get(tool, "36")
    return _c(color, f"[{tool:<7}]")

# ── Streaming subprocess runner ───────────────────────────────────────────────

def _stream_subprocess(
    cmd: list[str],
    tool: str,
    log_path: Path,
    output_queue: "queue.Queue[tuple[str, str] | None]",
) -> int:
    """
    Run *cmd* in a subprocess, read stdout+stderr line-by-line, put each line
    as (tool, line) onto *output_queue*, and write a full log to *log_path*.
    Returns the process exit code.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log_f:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ROOT,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            stripped = line.rstrip("\n")
            log_f.write(stripped + "\n")
            output_queue.put((tool, stripped))
        proc.wait()
    return proc.returncode

# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(
    tool: str,
    script: Path,
    non_interactive: bool,
    auto_install: bool,
    output_queue: "queue.Queue[tuple[str, str] | None]",
) -> tuple[str, int]:
    """Run one pipeline script, streaming its output through the queue."""
    cmd = [sys.executable, str(script), "--skip-prereqs"]
    if non_interactive:
        cmd.append("--non-interactive")
    if auto_install:
        cmd.append("--install")

    log_dir  = ROOT / "coverage-reports" / "logs"
    log_path = log_dir / f"{tool}.log"

    rc = _stream_subprocess(cmd, tool, log_path, output_queue)
    return tool, rc

# ── Output printer thread ─────────────────────────────────────────────────────

def printer_thread(q: "queue.Queue[tuple[str, str] | None]", done_event: threading.Event) -> None:
    """
    Drain the output queue and print prefixed lines until *done_event* is set
    and the queue is empty.
    """
    while not (done_event.is_set() and q.empty()):
        try:
            item = q.get(timeout=0.1)
        except queue.Empty:
            continue
        if item is None:
            break
        tool, line = item
        print(f"  {_tool_prefix(tool)}  {line}")
        sys.stdout.flush()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel coverage orchestrator")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Do not prompt for input")
    parser.add_argument("--install", action="store_true",
                        help="Auto-install missing tools (requires --non-interactive)")
    parser.add_argument("--skip-prereqs", action="store_true",
                        help="Skip prerequisite check")
    parser.add_argument("--tools", nargs="+",
                        choices=["gcov", "llvm", "opencpp", "microsoft"],
                        default=["gcov", "llvm", "opencpp", "microsoft"],
                        help="Which tool pipelines to run (default: all)")
    args = parser.parse_args()

    scripts_dir = ROOT / "scripts"

    # ── 0. Prerequisite check (sequential — must pass before launching) ───────
    if not args.skip_prereqs:
        print("\n  ══════════════════════════════════════════════════════════")
        print("  Coverage Demo — parallel run")
        print("  ══════════════════════════════════════════════════════════")
        print("\n  [0] Checking prerequisites ...")
        prereq_cmd = [sys.executable, str(scripts_dir / "check_prereqs.py")]
        if args.non_interactive:
            prereq_cmd.append("--non-interactive")
        if args.install:
            prereq_cmd.append("--install")
        result = subprocess.run(prereq_cmd, cwd=ROOT)
        if result.returncode != 0:
            print(_c("31", "\n  [ABORT] Prerequisite check reported errors."))
            return 1

    # ── Determine which pipelines to launch ───────────────────────────────────
    tool_scripts: dict[str, Path] = {
        "gcov":    scripts_dir / "run_gcov.py",
        "llvm":    scripts_dir / "run_llvm_cov.py",
        "opencpp": scripts_dir / "run_opencpp_coverage.py",
        "microsoft": scripts_dir / "run_microsoft_coverage.py",
    }
    requested = {t: tool_scripts[t] for t in args.tools}

    print(f"\n  [1-{len(requested)}] Launching pipelines in parallel: "
          f"{', '.join(requested)}")
    print(f"  Logs: {ROOT / 'coverage-reports' / 'logs'}\n")

    # ── Shared output queue + printer thread ──────────────────────────────────
    out_q: "queue.Queue[tuple[str, str] | None]" = queue.Queue()
    done_evt = threading.Event()
    printer  = threading.Thread(target=printer_thread, args=(out_q, done_evt), daemon=True)
    printer.start()

    # ── Launch all pipelines concurrently ─────────────────────────────────────
    results: dict[str, int] = {}
    t_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=len(requested)) as pool:
        futures: dict[Future, str] = {
            pool.submit(
                run_pipeline,
                tool, script,
                args.non_interactive, args.install,
                out_q,
            ): tool
            for tool, script in requested.items()
        }
        for future in as_completed(futures):
            tool_name, rc = future.result()
            results[tool_name] = rc

    elapsed = time.monotonic() - t_start

    # Signal printer thread to stop and wait for it
    done_evt.set()
    printer.join(timeout=2)

    # ── Generate landing page ─────────────────────────────────────────────────
    print(f"\n  ── Generating landing page {'─' * 30}")
    landing = subprocess.run(
        [sys.executable, str(scripts_dir / "generate_landing_page.py")],
        cwd=ROOT,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n  ══════════════════════════════════════════════════════════")
    print(f"  Summary  ({elapsed:.1f}s total)")
    print(f"  ══════════════════════════════════════════════════════════")

    final_rc = 0
    report_base = ROOT / "coverage-reports"
    tool_reports = {
        "gcov":    report_base / "gcov"    / "index.html",
        "llvm":    report_base / "llvm"    / "html" / "index.html",
        "opencpp": report_base / "opencpp" / "index.html",
        "microsoft": report_base / "microsoft" / "index.html",
    }

    for tool in args.tools:
        rc   = results.get(tool, -1)
        path = tool_reports[tool]
        if rc == 0:
            status = _c("32", "[OK]  ")
            detail = str(path) if path.exists() else "(no report file)"
        else:
            status = _c("31", "[FAIL]")
            detail = f"exit code {rc}"
            if tool not in {"opencpp", "microsoft"} or SYSTEM == "Windows":
                final_rc = 1
        label = {
            "gcov": "gcov / gcovr",
            "llvm": "llvm-cov",
            "opencpp": "OpenCppCoverage",
            "microsoft": "Microsoft Coverage",
        }[tool]
        print(f"  {status}  {label:<20} {detail}")

    if landing.returncode == 0:
        print(f"  {_c('32', '[OK]')}   Landing page       {report_base / 'index.html'}")
    else:
        print(f"  {_c('33', '[WARN]')} Landing page generation failed")

    print()
    return final_rc


if __name__ == "__main__":
    sys.exit(main())
