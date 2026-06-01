#!/usr/bin/env python3
"""
generate_merged_view.py
Reads per-line coverage data from all available tools and produces
coverage-reports/merged.html — a self-contained page with:
  - A file-list sidebar (click to show one file at a time)
  - Per-tool coverage indicator strips to the LEFT of the line number
  - A merged summary (lines covered by >= 1 tool)

Dynamic mode: tools are included only when their data files exist.
This means the page works correctly with 1, 2, or all 3 tools.

Apple-inspired light theme.
Tool accent colours — soft pastels, no green / orange / red:
  GCC  / gcov    ->  Periwinkle  #A7AAFF  (R167 G170 B255)
  LLVM / clang   ->  Mint        #54DFCB  (R84  G223 B203)
  MSVC / opencpp ->  Gold        #FEDF43  (R254 G223 B67)
"""

from __future__ import annotations

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
REPORTS = ROOT / "coverage-reports"
OUT     = REPORTS / "merged.html"

GCOV_LINES  = REPORTS / "gcov"    / "lines.json"
LLVM_LINES  = REPORTS / "llvm"    / "lines.json"
OPENCPP_XML = REPORTS / "opencpp" / "coverage.xml"

# ── Tool palette ──────────────────────────────────────────────────────────────

# Full registry — entries are only included in TOOLS at runtime when their
# data files actually exist (see _build_active_tools() below).
_ALL_TOOLS = ["gcov", "llvm", "opencpp"]

TOOL_LABEL = {"gcov": "GCC", "llvm": "LLVM", "opencpp": "MSVC"}
# Short tag labels shown inside each pill
TOOL_TAG   = {"gcov": "gcov", "llvm": "llvm-cov", "opencpp": "occ"}

# Soft pastel accents — periwinkle / mint / gold.
# Covered pill = solid accent fill.
# Missed pill  = same hue at ~22% opacity tint + accent border.
# Not-tracked  = no pill rendered (absence = not tracked).
TOOL_COLOR   = {"gcov": "#A7AAFF", "llvm": "#54DFCB", "opencpp": "#FEDF43"}
# Pre-computed 22%-opacity tints against #FFFFFF background
TOOL_MISS_BG = {"gcov": "#EDEEFF", "llvm": "#DDFAF5", "opencpp": "#FFFCD9"}
TOOL_HIT_FG  = {"gcov": "#1D1D1F", "llvm": "#1D1D1F", "opencpp": "#1D1D1F"}


def _build_active_tools() -> list[str]:
    """Return the subset of tools whose data files are present on disk."""
    active = []
    if GCOV_LINES.exists():
        active.append("gcov")
    if LLVM_LINES.exists():
        active.append("llvm")
    if OPENCPP_XML.exists():
        active.append("opencpp")
    if not active:
        # No data at all yet — return all so callers can still render empty state
        return list(_ALL_TOOLS)
    return active


# TOOLS is set after the path constants are defined (see bottom of section).

# ── Data types ─────────────────────────────────────────────────────────────────

# True = covered, False = instrumented but missed, None = not tracked by tool
Coverage = Dict[str, Dict[int, Dict[str, Optional[bool]]]]

# TOOLS is populated in main() once we know which data files exist.
TOOLS: list[str] = []


def empty_line_entry() -> Dict[str, Optional[bool]]:
    return {t: None for t in _ALL_TOOLS}


# ── Path normalisation ────────────────────────────────────────────────────────

def normalise(path: str) -> str:
    """Return a canonical relative key like 'src/calculator.cpp'."""
    s = path.replace("\\", "/")
    idx = s.find("/src/")
    if idx != -1:
        return "src/" + s[idx + 5:]
    p = Path(path)
    try:
        rel = p.resolve().relative_to(ROOT.resolve())
        rel_str = rel.as_posix()
        if rel_str.startswith("src/"):
            return rel_str
    except ValueError:
        pass
    return p.name


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_gcov(coverage: Coverage) -> None:
    if not GCOV_LINES.exists():
        print(f"[WARN] Not found: {GCOV_LINES}", file=sys.stderr)
        return
    with open(GCOV_LINES) as f:
        data = json.load(f)
    for file_entry in data.get("files", []):
        key = normalise(file_entry["file"])
        coverage.setdefault(key, {})
        for line in file_entry.get("lines", []):
            ln = line["line_number"]
            coverage[key].setdefault(ln, empty_line_entry())
            coverage[key][ln]["gcov"] = line["count"] > 0


def parse_llvm(coverage: Coverage) -> None:
    if not LLVM_LINES.exists():
        print(f"[WARN] Not found: {LLVM_LINES}", file=sys.stderr)
        return
    with open(LLVM_LINES) as f:
        data = json.load(f)
    for file_entry in data.get("data", [{}])[0].get("files", []):
        key = normalise(file_entry["filename"])
        coverage.setdefault(key, {})
        line_counts: Dict[int, int] = {}
        current_count = 0
        current_has = False
        for seg in file_entry.get("segments", []):
            seg_line, _col, count, has_count, _is_entry, _is_gap = seg
            if has_count:
                current_count = count
                current_has = True
            if current_has:
                ln = seg_line
                if ln not in line_counts:
                    line_counts[ln] = current_count
                else:
                    line_counts[ln] = max(line_counts[ln], current_count)
        for ln, count in line_counts.items():
            coverage[key].setdefault(ln, empty_line_entry())
            if coverage[key][ln]["llvm"] is None:
                coverage[key][ln]["llvm"] = count > 0
            elif count > 0:
                coverage[key][ln]["llvm"] = True


def parse_opencpp(coverage: Coverage) -> None:
    if not OPENCPP_XML.exists():
        print(f"[WARN] Not found: {OPENCPP_XML}", file=sys.stderr)
        return
    tree = ET.parse(OPENCPP_XML)
    for cls in tree.getroot().iter("class"):
        key = normalise(cls.attrib.get("filename", ""))
        if not key:
            continue
        coverage.setdefault(key, {})
        lines_el = cls.find("lines")
        if lines_el is None:
            continue
        for line_el in lines_el:
            ln = int(line_el.attrib["number"])
            hits = int(line_el.attrib.get("hits", 0))
            coverage[key].setdefault(ln, empty_line_entry())
            coverage[key][ln]["opencpp"] = hits > 0


# ── Source reader ─────────────────────────────────────────────────────────────

def read_source_files() -> Dict[str, List[str]]:
    sources: Dict[str, List[str]] = {}
    if not SRC_DIR.exists():
        return sources
    for path in sorted(SRC_DIR.rglob("*")):
        if path.suffix in (".cpp", ".hpp", ".h", ".cc", ".cxx"):
            rel = "src/" + path.relative_to(SRC_DIR).as_posix()
            try:
                sources[rel] = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception as e:
                print(f"[WARN] Cannot read {path}: {e}", file=sys.stderr)
    return sources


# ── Stats ─────────────────────────────────────────────────────────────────────

def file_merged_stats(line_data: Dict[int, Dict[str, Optional[bool]]]) -> Tuple[int, int]:
    covered = sum(1 for ld in line_data.values() if any(v is True  for v in ld.values()))
    total   = sum(1 for ld in line_data.values() if any(v is not None for v in ld.values()))
    return covered, total


# ── HTML row builder ──────────────────────────────────────────────────────────

def tags_cell(line_data: Optional[Dict[str, Optional[bool]]]) -> str:
    """One <td> per tool so each tool's pill occupies a fixed column.

    Covered  → solid accent fill  + dark text label
    Missed   → ghost pill (light tint bg + accent border + accent text)
    Not tracked → empty cell (absence communicates "tool doesn't know")
    """
    if line_data is None:
        ld = {t: None for t in TOOLS}
    else:
        ld = line_data

    cells = []
    for t in TOOLS:
        state = ld[t]
        tag   = TOOL_TAG[t]
        color = TOOL_COLOR[t]
        if state is True:
            pill = (
                f'<span class="tag tag-hit" '
                f'style="background:{color};border-color:{color};" '
                f'title="{TOOL_LABEL[t]}: covered">{tag}</span>'
            )
        elif state is False:
            pill = (
                f'<span class="tag tag-miss" '
                f'style="background:{TOOL_MISS_BG[t]};border-color:{color};color:{color};" '
                f'title="{TOOL_LABEL[t]}: not covered">{tag}</span>'
            )
        else:
            pill = ""  # not tracked → empty cell
        cells.append(f'<td class="tag-cell tag-cell-{t}">{pill}</td>')

    return "".join(cells)


def source_row(ln: int, src_line: str, line_data: Optional[Dict[str, Optional[bool]]]) -> str:
    ld = line_data or {t: None for t in TOOLS}

    any_hit  = any(v is True  for v in ld.values())
    any_miss = any(v is False for v in ld.values())

    if any_hit:
        row_class = "row-hit"
    elif any_miss:
        row_class = "row-miss"
    else:
        row_class = "row-plain"

    src_escaped = html.escape(src_line.rstrip("\n"), quote=False)
    leading = len(src_escaped) - len(src_escaped.lstrip())
    if leading:
        src_escaped = "\u00a0" * leading + src_escaped[leading:]

    return (
        f'<tr class="{row_class}">'
        + tags_cell(ld)
        + f'<td class="ln">{ln}</td>'
        + f'<td class="src"><code>{src_escaped}</code></td>'
        + "</tr>"
    )


# ── Per-file HTML block ───────────────────────────────────────────────────────

def file_block(rel_path: str, source_lines: List[str], line_data: Dict[int, Dict[str, Optional[bool]]]) -> str:
    covered, total = file_merged_stats(line_data)
    pct = (covered / total * 100) if total else 0.0
    file_id = "f_" + re.sub(r"[^a-zA-Z0-9]", "_", rel_path)

    # Pill badges per tool
    tool_badges = []
    for t in TOOLS:
        hits   = sum(1 for ld in line_data.values() if ld.get(t) is True)
        missed = sum(1 for ld in line_data.values() if ld.get(t) is False)
        color  = TOOL_COLOR[t]
        if hits + missed == 0:
            tool_badges.append(
                f'<span class="badge badge-na">'
                f'{TOOL_LABEL[t]} <span class="badge-val">—</span></span>'
            )
        else:
            p = hits / (hits + missed) * 100
            tool_badges.append(
                f'<span class="badge" style="border-color:{color};background:{TOOL_MISS_BG[t]};">'
                f'{TOOL_LABEL[t]} <span class="badge-val">{p:.0f}%</span></span>'
            )
    badges_html = "".join(tool_badges)

    header_tags = "".join(
        f'<th class="th-tag th-tag-{t}">{TOOL_TAG[t]}</th>'
        for t in TOOLS
    )

    rows = []
    for i, src_line in enumerate(source_lines):
        ln = i + 1
        rows.append(source_row(ln, src_line, line_data.get(ln)))

    return f"""<div class="file-panel" id="{file_id}">
  <div class="file-header">
    <div class="file-title">
      <span class="file-path">{html.escape(rel_path)}</span>
      <span class="merged-badge">
        Merged&nbsp;<strong>{covered}/{total}</strong>&nbsp;lines&nbsp;
        <span class="pct" style="background:{TOOL_MISS_BG['gcov']};color:{TOOL_COLOR['gcov']};">{pct:.1f}%</span>
      </span>
    </div>
    <div class="tool-badges">{badges_html}</div>
  </div>
  <div class="table-scroll">
  <table class="src-table">
    <thead>
      <tr>
        {header_tags}
        <th class="th-ln">LN</th>
        <th class="th-src">Source</th>
      </tr>
    </thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  </div>
</div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; }
html, body { height: 100%; margin: 0; font-size: 14px; }
body {
  font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
  background: #F5F5F7;
  color: #1D1D1F;
  display: flex;
  flex-direction: column;
}

/* ── Top bar ── */
.topbar {
  background: rgba(255,255,255,0.85);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid #D2D2D7;
  padding: .65rem 1.2rem;
  display: flex;
  align-items: baseline;
  gap: 1rem;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.topbar h1 { margin: 0; font-size: 1rem; font-weight: 600; color: #1D1D1F; }
.topbar .subtitle { font-size: .78rem; color: #86868B; }

/* ── Legend ── */
.legend {
  background: #FFFFFF;
  border-bottom: 1px solid #E5E5EA;
  padding: .4rem 1.2rem;
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  font-size: .76rem;
  color: #3A3A3C;
  flex-shrink: 0;
}
.legend-item { display: flex; align-items: center; gap: .5rem; }

/* ── Layout ── */
.layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

/* ── Sidebar ── */
.sidebar {
  width: 210px;
  min-width: 170px;
  background: #FFFFFF;
  border-right: 1px solid #D2D2D7;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar-header {
  padding: .55rem .9rem;
  font-size: .68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #86868B;
  border-bottom: 1px solid #E5E5EA;
  flex-shrink: 0;
}
.sidebar-list { list-style: none; margin: 0; padding: .3rem 0; overflow-y: auto; flex: 1; }
.sidebar-list li { padding: 0; }
.sidebar-list a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .42rem .9rem;
  font-size: .82rem;
  color: #3A3A3C;
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: background .1s;
  gap: .4rem;
}
.sidebar-list a:hover { background: #F5F5F7; }
.sidebar-list a.active {
  background: #EBF3FF;
  color: #0071E3;
  border-left-color: #0071E3;
  font-weight: 600;
}
.sidebar-fname {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: .78rem;
}
.sidebar-pct {
  font-size: .7rem;
  color: #86868B;
  flex-shrink: 0;
}
.sidebar-list a.active .sidebar-pct { color: #0071E3; opacity: .7; }

/* ── Main panel ── */
.main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── File panels ── */
.file-panel {
  display: none;
  flex-direction: column;
  height: 100%;
}
.file-panel.visible {
  display: flex;
}

/* ── File header ── */
.file-header {
  background: #FFFFFF;
  border-bottom: 1px solid #E5E5EA;
  padding: .55rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: .5rem;
}
.file-title {
  display: flex;
  align-items: center;
  gap: .75rem;
  min-width: 0;
}
.file-path {
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  font-size: .82rem;
  font-weight: 600;
  color: #1D1D1F;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.merged-badge {
  font-size: .75rem;
  color: #6E6E73;
  white-space: nowrap;
}
.pct {
  display: inline-block;
  padding: .1rem .4rem;
  border-radius: 20px;
  font-weight: 700;
  font-size: .72rem;
}
.tool-badges { display: flex; gap: .4rem; flex-wrap: wrap; }
.badge {
  display: inline-block;
  padding: .15rem .55rem;
  border-radius: 20px;
  border: 1.5px solid;
  font-size: .72rem;
  font-weight: 500;
  background: #FFFFFF;
  white-space: nowrap;
}
.badge-na { color: #AEAEB2 !important; }
.badge-val { font-weight: 700; color: #1D1D1F; }

/* ── Source table ── */
.table-scroll { overflow: auto; flex: 1; }
.src-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: .8rem;
  background: #FFFFFF;
}
.src-table thead th {
  background: #F5F5F7;
  border-bottom: 1px solid #E5E5EA;
  padding: .3rem .3rem;
  font-size: .65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  position: sticky;
  top: 0;
  z-index: 5;
}
/* Column widths: tags fixed, line-number fixed, source fills the rest */
.th-tags { text-align: left; width: 178px; white-space: nowrap; padding-left: .6rem !important; }
.th-ln  { text-align: right; width: 3.2rem; color: #86868B; padding-right: .6rem !important; }
.th-src { text-align: left; padding-left: .5rem !important; }

/* Per-tool tag column widths */
.th-tag, .tag-cell {
  text-align: center;
  padding: 0 .25rem !important;
  vertical-align: middle;
  height: 1.6rem;
}
.th-tag {
  font-size: .65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: #86868B;
}
/* Per-tool tag column widths — overridden dynamically from Python */
.th-tag-gcov,    .tag-cell-gcov    { width: 56px;  border-right: none; }
.th-tag-llvm,    .tag-cell-llvm    { width: 74px;  border-right: none; }
.th-tag-opencpp, .tag-cell-opencpp { width: 50px;  border-right: 1px solid #E5E5EA; }

/* ── Table rows ── */
.src-table td { padding: .08rem .25rem; vertical-align: middle; height: 1.6rem; }
.row-plain td { background: #FFFFFF; }
.row-hit   td { background: #F0F7FF; }
.row-miss  td { background: #FFF8F0; }
.src-table tbody tr:hover td { background: #EEF4FB !important; }
.tag {
  display: inline-block;
  padding: .1rem .38rem;
  border-radius: 4px;
  border: 1.5px solid;
  font-size: .68rem;
  font-weight: 600;
  letter-spacing: .01em;
  margin-right: .22rem;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  line-height: 1.4;
  vertical-align: middle;
}
.tag-hit  { color: #1D1D1F; }
.tag-miss { /* border-color and bg set inline */ }

/* ── Line number ── */
.ln {
  text-align: right;
  color: #AEAEB2;
  user-select: none;
  padding-right: .7rem !important;
  padding-left: .3rem !important;
  width: 3.2rem;
  border-right: 1px solid #E5E5EA;
  vertical-align: middle;
}

/* ── Source code ── */
.src { padding-left: .6rem !important; }
.src code { white-space: pre; color: #1D1D1F; }

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #86868B;
  font-size: .9rem;
  gap: .5rem;
}
.empty-state .hint { font-size: .78rem; color: #AEAEB2; }
"""

# ── JS ────────────────────────────────────────────────────────────────────────

JS = """
function showFile(id) {
  // Hide all panels, show selected
  document.querySelectorAll('.file-panel').forEach(p => p.classList.remove('visible'));
  var panel = document.getElementById(id);
  if (panel) {
    panel.classList.add('visible');
    // Scroll table back to top
    var scroll = panel.querySelector('.table-scroll');
    if (scroll) scroll.scrollTop = 0;
  }
  // Update sidebar active state
  document.querySelectorAll('.sidebar-list a').forEach(a => {
    a.classList.toggle('active', a.dataset.target === id);
  });
  // Persist selection
  try { sessionStorage.setItem('mergedFile', id); } catch(e) {}
}

// On load: restore last selection or show first file
(function() {
  var links = document.querySelectorAll('.sidebar-list a');
  if (!links.length) return;
  var last = null;
  try { last = sessionStorage.getItem('mergedFile'); } catch(e) {}
  var target = last && document.getElementById(last) ? last : links[0].dataset.target;
  showFile(target);
})();
"""


def _tool_col_css(tools: list[str]) -> str:
    """Generate .th-tag-X / .tag-cell-X width rules for only the active tools."""
    # widths per tool — last active tool gets the separator border
    widths = {"gcov": 56, "llvm": 74, "opencpp": 50}
    rules = []
    for i, t in enumerate(tools):
        w = widths.get(t, 60)
        border = "border-right: 1px solid #E5E5EA;" if i == len(tools) - 1 else "border-right: none;"
        rules.append(
            f".th-tag-{t}, .tag-cell-{t} {{ width: {w}px; {border} }}"
        )
    return "\n".join(rules)


# ── Full page ─────────────────────────────────────────────────────────────────

def build_page(sources: Dict[str, List[str]], coverage: Coverage, tools: list[str]) -> str:
    all_files = sorted(set(sources.keys()) | set(coverage.keys()))

    # Sidebar
    sidebar_items = []
    for rel in all_files:
        ld = coverage.get(rel, {})
        covered, total = file_merged_stats(ld)
        pct_str = f"{covered/total*100:.0f}%" if total else "—"
        file_id = "f_" + re.sub(r"[^a-zA-Z0-9]", "_", rel)
        short = Path(rel).name
        sidebar_items.append(
            f'<li><a href="javascript:void(0)" data-target="{file_id}" '
            f'onclick="showFile(\'{file_id}\')" title="{html.escape(rel)}">'
            f'<span class="sidebar-fname">{html.escape(short)}</span>'
            f'<span class="sidebar-pct">{pct_str}</span>'
            f'</a></li>'
        )

    # File panels
    panels = []
    for rel in all_files:
        src_lines = sources.get(rel, [])
        ld = coverage.get(rel, {})
        panels.append(file_block(rel, src_lines, ld))

    # Legend — show actual tag pills as examples
    legend_parts = []
    for t in TOOLS:
        color = TOOL_COLOR[t]
        tag   = TOOL_TAG[t]
        legend_parts.append(
            f'<span class="legend-item">'
            f'<span class="tag tag-hit" style="background:{color};border-color:{color};">{tag}</span>'
            f'covered'
            f'</span>'
        )
        legend_parts.append(
            f'<span class="legend-item">'
            f'<span class="tag tag-miss" style="background:{TOOL_MISS_BG[t]};border-color:{color};color:{color};">{tag}</span>'
            f'not covered'
            f'</span>'
        )
    legend_parts.append(
        '<span class="legend-item" style="color:#AEAEB2;">'
        '<span style="font-size:.75rem;margin-right:.3rem;">∅</span>'
        'not tracked by tool'
        '</span>'
    )

    tool_names = " / ".join(TOOL_LABEL[t] for t in tools)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Dynamic tool CSS overrides
    tool_col_css = _tool_col_css(tools)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Coverage — Merged View</title>
  <style>{CSS}
/* ── Dynamic tool column widths ── */
{tool_col_css}
  </style>
</head>
<body>

<div class="topbar">
  <h1>Coverage &mdash; Merged View</h1>
  <span class="subtitle">Generated {date_str} &mdash; line-level comparison across {tool_names}</span>
</div>

<div class="legend">
  {"".join(legend_parts)}
</div>

<div class="layout">

  <nav class="sidebar">
    <div class="sidebar-header">Source files</div>
    <ul class="sidebar-list">
      {"".join(sidebar_items)}
    </ul>
  </nav>

  <main class="main">
    {"".join(panels)}
    <div class="empty-state" id="empty-state" style="display:none;">
      <span>No file selected</span>
      <span class="hint">Click a file in the sidebar to view coverage</span>
    </div>
  </main>

</div>

<script>{JS}</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    global TOOLS
    TOOLS = _build_active_tools()

    coverage: Coverage = {}
    parse_gcov(coverage)
    parse_llvm(coverage)
    parse_opencpp(coverage)

    sources = read_source_files()

    if not coverage and not sources:
        print("[ERROR] No coverage data and no source files found.", file=sys.stderr)
        return 1

    page = build_page(sources, coverage, TOOLS)
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    active_tools = ", ".join(TOOL_LABEL[t] for t in TOOLS)
    print(f"Merged view written: {OUT}  (tools: {active_tools})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
