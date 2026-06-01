#!/usr/bin/env python3
"""
generate_landing_page.py
Parses coverage summary files produced by the available tools and generates
coverage-reports/index.html — a self-contained landing page with:
  - A comparison table (line / branch / function % per available tool)
  - Direct links to each tool's full HTML report
  - Colour-coded cells (green ≥ 80 %, amber ≥ 60 %, red < 60 %)
  - A methodology note for each tool

Dynamic mode: only tools whose summary files exist are shown.
This means the page works correctly with 1, 2, or all 3 tools.
"""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────

ROOT         = Path(__file__).resolve().parent.parent
REPORTS      = ROOT / "coverage-reports"
OUT_HTML     = REPORTS / "index.html"
VENV_DIR     = ROOT / ".coverage-venv"

OPENCPP_XML  = REPORTS / "opencpp"  / "coverage.xml"
GCOV_JSON    = REPORTS / "gcov"     / "summary.json"
LLVM_JSON    = REPORTS / "llvm"     / "summary.json"

OPENCPP_HREF = "opencpp/index.html"
GCOV_HREF    = "gcov/index.html"
LLVM_HREF    = "llvm/html/index.html"


def venv_python() -> Optional[Path]:
    if sys.platform.startswith("win"):
        candidate = VENV_DIR / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIR / "bin" / "python3"
    return candidate if candidate.exists() else None

# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    name:         str
    href:         str
    css_class:    str                  # "opencpp" | "gcov" | "llvm"
    accent:       str                  # accent colour hex
    line_pct:     Optional[float] = None
    branch_pct:   Optional[float] = None
    function_pct: Optional[float] = None
    available:    bool            = False
    notes:        str             = ""


# ── Parsers ──────────────────────────────────────────────────────────────────

def parse_opencpp(path: Path) -> ToolResult:
    result = ToolResult(
        name="OpenCppCoverage",
        href=OPENCPP_HREF,
        css_class="opencpp",
        accent="#FEDF43",
        notes="Line coverage only via debug-info (PDB). "
              "Branch and function metrics not produced by this tool.",
    )
    if not path.exists():
        print(f"[INFO] Not found (skipped): {path}")
        return result
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        line_rate = root.attrib.get("line-rate")
        if line_rate is not None:
            result.line_pct = round(float(line_rate) * 100.0, 1)
        result.available = True
    except Exception as exc:
        print(f"[WARN] Could not parse {path}: {exc}")
    return result


def parse_gcov(path: Path) -> ToolResult:
    result = ToolResult(
        name="gcov / gcovr",
        href=GCOV_HREF,
        css_class="gcov",
        accent="#A7AAFF",
        notes="Line + branch + function coverage via GCC --coverage instrumentation. "
              "Reports source-mapped data including header-only functions.",
    )
    if not path.exists():
        print(f"[INFO] Not found (skipped): {path}")
        return result
    try:
        with open(path) as f:
            data = json.load(f)
        result.line_pct     = round(data.get("line_percent",     0.0), 1)
        result.branch_pct   = round(data.get("branch_percent",   0.0), 1)
        result.function_pct = round(data.get("function_percent", 0.0), 1)
        result.available    = True
    except Exception as exc:
        print(f"[WARN] Could not parse {path}: {exc}")
    return result


def parse_llvm(path: Path) -> ToolResult:
    result = ToolResult(
        name="llvm-cov (Clang)",
        href=LLVM_HREF,
        css_class="llvm",
        accent="#54DFCB",
        notes="Line + branch + function + region coverage via source-based instrumentation. "
              "Most granular: can show per-instantiation template coverage.",
    )
    if not path.exists():
        print(f"[INFO] Not found (skipped): {path}")
        return result
    try:
        with open(path) as f:
            data = json.load(f)
        result.line_pct     = round(data.get("line_percent",     0.0), 1)
        result.branch_pct   = round(data.get("branch_percent",   0.0), 1)
        result.function_pct = round(data.get("function_percent", 0.0), 1)
        result.available    = True
    except Exception as exc:
        print(f"[WARN] Could not parse {path}: {exc}")
    return result


# ── HTML helpers ─────────────────────────────────────────────────────────────

def pct_cell(value: Optional[float]) -> str:
    if value is None:
        return '<td class="na">N/A</td>'
    if value >= 80.0:
        color = "#4CD964"
    elif value >= 60.0:
        color = "#FFB340"
    else:
        color = "#FF6961"
    return (
        f'<td style="background:{color}D0;color:#1D1D1F;font-weight:bold;'
        f'text-align:center;">{value:.1f}%</td>'
    )


def tool_row(r: ToolResult) -> str:
    if r.available:
        name_cell = f'<td><a href="{r.href}" target="_blank">{r.name}</a></td>'
    else:
        name_cell = f'<td class="na">{r.name} (not available)</td>'
    return (
        "<tr>"
        + name_cell
        + pct_cell(r.line_pct)
        + pct_cell(r.branch_pct)
        + pct_cell(r.function_pct)
        + "</tr>"
    )


def tool_card(r: ToolResult) -> str:
    link_cls = "" if r.available else 'class="disabled"'
    return f"""\
    <div class="card {r.css_class}">
      <h3>{r.name}</h3>
      <p>{r.notes}</p>
      <a href="{r.href}" {link_cls}>Open Report</a>
    </div>"""


# ── HTML template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>C++ Coverage Comparison</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; }}
    body {{
      font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
      background: #F5F5F7;
      color: #1D1D1F;
      display: flex;
      flex-direction: column;
    }}
    /* ── Tab bar ── */
    .tabbar {{
      display: flex;
      align-items: center;
      background: rgba(255,255,255,0.9);
      backdrop-filter: saturate(180%) blur(20px);
      -webkit-backdrop-filter: saturate(180%) blur(20px);
      border-bottom: 1px solid #D2D2D7;
      padding: 0 1.5rem;
      gap: .15rem;
      flex-shrink: 0;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .tabbar h1 {{
      color: #1D1D1F;
      font-size: 1rem;
      font-weight: 600;
      margin: 0 1.5rem 0 0;
      padding: .7rem 0;
      white-space: nowrap;
    }}
    .tab {{
      padding: .65rem 1.1rem;
      border: none;
      border-bottom: 2px solid transparent;
      cursor: pointer;
      font-size: .85rem;
      color: #86868B;
      background: transparent;
      transition: color .15s, border-color .15s;
      font-family: inherit;
    }}
    .tab:hover {{ color: #1D1D1F; }}
    .tab.active {{
      color: #0071E3;
      border-bottom-color: #0071E3;
      font-weight: 600;
    }}
    /* ── Tab panels ── */
    .panel {{ display: none; padding: 2rem; flex: 1; overflow-y: auto; }}
    .panel.active {{ display: block; }}
    /* ── Comparison table ── */
    .comparison {{
      width: 100%;
      max-width: 760px;
      border-collapse: collapse;
      margin-bottom: 2.5rem;
      background: #FFFFFF;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 2px 12px rgba(0,0,0,.08);
    }}
    .comparison th {{
      background: #F5F5F7;
      color: #86868B;
      padding: .7rem 1rem;
      text-align: left;
      font-size: .75rem;
      text-transform: uppercase;
      letter-spacing: .06em;
      border-bottom: 1px solid #E5E5EA;
    }}
    .comparison td {{
      padding: .7rem 1rem;
      border-bottom: 1px solid #F2F2F7;
      font-size: .9rem;
      color: #1D1D1F;
    }}
    .comparison tr:last-child td {{ border-bottom: none; }}
    .comparison a {{ color: #0071E3; text-decoration: none; }}
    .comparison a:hover {{ text-decoration: underline; }}
    td.na {{ color: #AEAEB2; font-style: italic; text-align: center; }}
    /* ── Tool cards ── */
    .cards {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      max-width: 900px;
      margin-bottom: 2.5rem;
    }}
    .card {{
      flex: 1 1 260px;
      background: #FFFFFF;
      border-radius: 12px;
      padding: 1.25rem;
      box-shadow: 0 2px 12px rgba(0,0,0,.08);
      border-top: 4px solid;
    }}
    .card.opencpp {{ border-color: #FEDF43; }}
    .card.gcov     {{ border-color: #A7AAFF; }}
    .card.llvm     {{ border-color: #54DFCB; }}
    .card h3 {{ margin: 0 0 .5rem; font-size: .95rem; color: #1D1D1F; }}
    .card p  {{ margin: 0; font-size: .82rem; color: #6E6E73; line-height: 1.55; }}
    .card a  {{
      display: inline-block;
      margin-top: .85rem;
      padding: .4rem .9rem;
      border-radius: 20px;
      text-decoration: none;
      font-size: .82rem;
      font-weight: 600;
    }}
    .card.opencpp a {{ background: #FEDF43; color: #1D1D1F; }}
    .card.gcov     a {{ background: #A7AAFF; color: #1D1D1F; }}
    .card.llvm     a {{ background: #54DFCB; color: #1D1D1F; }}
    .card a.disabled {{
      background: #E5E5EA;
      color: #AEAEB2;
      cursor: not-allowed;
      pointer-events: none;
    }}
    /* ── Legend ── */
    .legend {{ display: flex; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }}
    .legend-item {{
      display: flex; align-items: center; gap: .4rem; font-size: .8rem; color: #3A3A3C;
    }}
    .swatch {{
      width: 12px; height: 12px; border-radius: 3px; display: inline-block;
    }}
    /* ── Merged panel iframe ── */
    .merged-frame {{
      width: 100%;
      height: calc(100vh - 90px);
      border: 1px solid #D2D2D7;
      border-radius: 10px;
      background: #F5F5F7;
    }}
    .subtitle {{ color: #86868B; margin-bottom: 1.5rem; font-size: .85rem; }}
    footer {{ margin-top: 3rem; font-size: .73rem; color: #AEAEB2; }}
  </style>
</head>
<body>

<div class="tabbar">
  <h1>C++ Coverage</h1>
  <button class="tab active" onclick="showTab('summary', this)">Summary</button>
  <button class="tab"        onclick="showTab('merged',  this)">Merged View</button>
</div>

<!-- ── Tab: Summary ─────────────────────────────────────────────────────── -->
<div id="tab-summary" class="panel active">
  <p class="subtitle">Generated {date} &mdash; {tool_list}</p>

  <div class="legend">
    <span class="legend-item"><span class="swatch" style="background:#4CD964"></span>&ge; 80 % &mdash; good</span>
    <span class="legend-item"><span class="swatch" style="background:#FFB340"></span>&ge; 60 % &mdash; acceptable</span>
    <span class="legend-item"><span class="swatch" style="background:#FF6961"></span>&lt; 60 % &mdash; low</span>
  </div>

  <table class="comparison">
    <thead>
      <tr>
        <th>Tool</th>
        <th>Line %</th>
        <th>Branch %</th>
        <th>Function %</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>

  <div class="cards">
{cards}
  </div>

  <footer>
    Source: <code>scripts/generate_landing_page.py</code> &mdash;
    Parsed from <code>coverage-reports/*/summary.json</code>
    and <code>coverage-reports/opencpp/coverage.xml</code>
  </footer>
</div>

<!-- ── Tab: Merged View ─────────────────────────────────────────────────── -->
<div id="tab-merged" class="panel">
  <iframe class="merged-frame" src="merged.html" title="Merged coverage view"></iframe>
</div>

<script>
function showTab(name, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}}
</script>

</body>
</html>
"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)

    opencpp = parse_opencpp(OPENCPP_XML)
    gcov    = parse_gcov(GCOV_JSON)
    llvm    = parse_llvm(LLVM_JSON)

    all_tools = [opencpp, gcov, llvm]

    # Only include available tools in the table and cards
    available = [t for t in all_tools if t.available]
    if not available:
        print("[WARN] No tool results found — landing page will show empty state")
        # Still generate the page so CI doesn't fail
        available = all_tools

    rows  = "\n".join(f"    {tool_row(r)}" for r in available)
    cards = "\n".join(tool_card(r) for r in available)

    tool_list = " &bull; ".join(r.name for r in available)

    page = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        tool_list=tool_list,
        rows=rows,
        cards=cards,
    )

    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"Landing page written: {OUT_HTML}")

    # ── Generate merged view ──────────────────────────────────────────────────
    merged_script = Path(__file__).parent / "generate_merged_view.py"
    if merged_script.exists():
        python_bin = venv_python() or Path(sys.executable)
        result = subprocess.run(
            [str(python_bin), str(merged_script)],
            capture_output=False,
        )
        if result.returncode != 0:
            print("[WARN] Merged view generation failed.", file=sys.stderr)
    else:
        print(f"[WARN] {merged_script} not found — merged view skipped.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
