"""
Turn benchmark JSON into LaTeX macros, so no number in the report is typed by hand.

The rule this enforces: a figure in the paper either came out of a benchmark or it
renders as a bold `??` on the page where nobody can miss it. There is no third
state, and in particular there is no state where a plausible number sits in a
table because somebody remembered it roughly during a late night.

How it works. Every scalar in `results/*.json` becomes a macro named from its file
and key — `accumulator.json` with `epochProofSpeedup` becomes `resAccumulatorEpochProofSpeedup`.
The paper never writes that name directly; it writes

    \\num{AccumulatorEpochProofSpeedup}

and `\\num` resolves it if it exists and prints `??` if it does not. That
indirection is the whole point: adding a measurement fills a hole in the PDF
without touching the prose, and removing one puts the hole back rather than
leaving a stale figure behind.

Series — anything indexed by a parameter — become tabular row bodies instead, so a
table's shape lives in the paper and its contents live here.

Run:  python -m model.bench.to_latex
"""

from __future__ import annotations

import json
import re
from typing import Any

from .harness import REPO_ROOT, RESULTS_DIR

OUTPUT = REPO_ROOT / "results.tex"
INDEX = REPO_ROOT / "results" / "INDEX.md"

PREAMBLE = r"""% =============================================================================
%  results.tex — GENERATED. Do not edit.
%
%  Regenerate with:  python -m model.bench.to_latex   (from "Breadcrumbs Project")
%
%  Every macro below was produced by a benchmark in model/bench/. The paper refers
%  to them through \num{Name}, which prints the measurement if it exists and a
%  bold ?? if it does not — so an unmeasured number is visible on the page rather
%  than quietly absent.
% =============================================================================

\providecommand{\num}[1]{%
  \ifcsname res#1\endcsname\csname res#1\endcsname\else\textbf{??}\fi}
\providecommand{\numunit}[2]{%
  \ifcsname res#1\endcsname\csname res#1\endcsname\,#2\else\textbf{??}\fi}
\providecommand{\rows}[1]{%
  \ifcsname rows#1\endcsname\csname rows#1\endcsname\else
  \multicolumn{1}{l}{\textbf{?? not measured}}\\\fi}

"""


def _camel(text: str) -> str:
    """Turn any label into a LaTeX-safe CamelCase name: letters only, no digits."""
    words = re.split(r"[^A-Za-z0-9]+", text)
    out = "".join(w[:1].upper() + w[1:] for w in words if w)
    # LaTeX command names cannot contain digits, so spell them out.
    digits = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four",
              "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}
    return "".join(digits.get(c, c) for c in out)


def _fmt(value: Any) -> str:
    """
    Render a value for the page.

    Thousands separators go in with a thin space rather than a comma, because a
    comma is a decimal point in much of the world and this report is read in
    Bangladesh and in Europe.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}".replace(",", "\\,")
    if isinstance(value, float):
        if value >= 100:
            return f"{value:,.0f}".replace(",", "\\,")
        if value >= 10:
            return f"{value:.1f}"
        if value >= 1:
            return f"{value:.2f}"
        return f"{value:.3f}"
    return str(value).replace("_", "\\_").replace("%", "\\%")


def build() -> tuple[str, list[tuple[str, str, str]]]:
    """Returns (latex, index rows) where an index row is (macro, value, source)."""
    lines = [PREAMBLE]
    index: list[tuple[str, str, str]] = []

    for path in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        name = _camel(data.get("name", path.stem))
        lines.append(f"% ---- {path.name}: {data.get('description', '')}")

        for key, entry in sorted(data.get("values", {}).items()):
            macro = f"res{name}{_camel(key)}"
            value = _fmt(entry["value"] if isinstance(entry, dict) else entry)
            lines.append(f"\\expandafter\\def\\csname {macro}\\endcsname{{{value}}}")
            index.append((macro, value, path.name))

        for timing in data.get("timings", []):
            macro = f"res{name}{_camel(timing['label'])}Ms"
            value = _fmt(timing["median_ms"])
            lines.append(f"\\expandafter\\def\\csname {macro}\\endcsname{{{value}}}")
            index.append((macro, value, path.name))

        for series_name, rows in sorted(data.get("series", {}).items()):
            if not rows:
                continue
            macro = f"rows{name}{_camel(series_name)}"
            columns = list(rows[0].keys())
            body = " \\\\\n".join(
                " & ".join(_fmt(row.get(c, "")) for c in columns) for row in rows
            )
            lines.append(f"% columns: {', '.join(columns)}")
            lines.append(f"\\expandafter\\def\\csname {macro}\\endcsname{{%\n{body} \\\\}}")
            index.append((macro, f"{len(rows)} rows: {', '.join(columns)}", path.name))

        machine = data.get("machine", {})
        macro = f"res{name}Machine"
        lines.append(
            f"\\expandafter\\def\\csname {macro}\\endcsname"
            f"{{{_fmt(machine.get('platform', 'unknown'))}}}"
        )
        index.append((macro, machine.get("platform", "unknown"), path.name))
        lines.append("")

    return "\n".join(lines) + "\n", index


def main() -> None:
    if not RESULTS_DIR.exists():
        raise SystemExit(f"no results directory at {RESULTS_DIR}; run a benchmark first")

    latex, index = build()
    OUTPUT.write_text(latex)

    rows = [
        "# Available measurements",
        "",
        "Generated by `python -m model.bench.to_latex`. The paper refers to these",
        "through `\\num{Name}` — drop the `res` prefix. Anything not listed here",
        "renders as a bold `??` in the PDF.",
        "",
        "| Macro | Value | Source |",
        "|---|---|---|",
    ]
    for macro, value, source in index:
        rows.append(f"| `\\num{{{macro[3:]}}}` | {value} | `{source}` |")
    INDEX.write_text("\n".join(rows) + "\n")

    print(f"wrote {OUTPUT}  ({len(index)} macros)")
    print(f"wrote {INDEX}")


if __name__ == "__main__":
    main()
