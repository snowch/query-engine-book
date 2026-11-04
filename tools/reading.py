"""Static views of the same generated evidence the optional experiments use.

These functions format reports; they never run an engine or estimate a measurement.
"""

from __future__ import annotations

import html
import math


def esc(value) -> str:
    return html.escape(str(value))


def number(value) -> str:
    return f"{value:,}" if isinstance(value, (int, float)) else esc(value)


def table(headings, rows) -> str:
    head = "".join(f'<th scope="col">{esc(h)}</th>' for h in headings)
    body = "".join(
        "<tr>"
        + "".join(f'<td data-label="{esc(h)}">{number(v)}</td>' for h, v in zip(headings, row, strict=True))
        + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def chart(data: dict) -> str:
    """A labelled SVG and its exact data, including the report's logarithmic x axis."""
    series = data["series"]
    points = [p for s in series for p in s["points"]]
    if not points:
        return ""
    log = data.get("x_scale") == "log"
    transform = math.log10 if log else float
    lo, hi = min(transform(p[0]) for p in points), max(transform(p[0]) for p in points)
    ymax = max(p[1] for p in points) or 1
    x = lambda v: 65 + 535 * (transform(v) - lo) / (hi - lo or 1)  # noqa: E731
    y = lambda v: 200 - 170 * v / ymax  # noqa: E731
    lines = []
    legend = []
    for i, s in enumerate(series):
        dash = ["none", "8 4", "2 4", "10 3 2 3"][i % 4]
        colour = ["var(--accent)", "var(--go)", "var(--stop)", "var(--muted)"][i % 4]
        coords = " ".join(f"{x(a):.2f},{y(b):.2f}" for a, b in s["points"])
        lines.append(
            f'<polyline points="{coords}" fill="none" stroke="{colour}" stroke-width="2.5" stroke-dasharray="{dash}"/>'
        )
        legend.append(
            f'<span><svg viewBox="0 0 32 8" aria-hidden="true"><path d="M0 4H32" stroke="{colour}" stroke-width="3" stroke-dasharray="{dash}"/></svg>{esc(s["label"])}</span>'
        )
    ticks = ""
    values = {p[0] for p in points}
    labels = {
        min(values, key=lambda v: abs(transform(v) - (lo + (hi - lo) * fraction)))
        for fraction in (0, 0.25, 0.5, 0.75, 1)
    }
    for v in sorted(labels):
        ticks += f'<text class="{"end-tick" if v in (min(values), max(values)) else "intermediate-tick"}" x="{x(v)}" y="220" text-anchor="{"start" if v == min(values) else "end" if v == max(values) else "middle"}">{number(v)}</text>'
    title = f"{data['y_label']} by {data['x_label']}"
    rows = [(s["label"], a, b) for s in series for a, b in s["points"]]
    return (
        f'<figure class="reading-chart"><figcaption>{esc(title)}</figcaption>'
        f'<svg viewBox="0 0 640 260" role="img" aria-label="{esc(title)}; exact values in the data table below">'
        '<path d="M65 25V200H605" fill="none" stroke="currentColor" opacity=".4"/>'
        f'<text x="65" y="20">{number(ymax)}</text>'
        f'<text x="58" y="204" text-anchor="end">0</text>{ticks}{"".join(lines)}'
        f'<text x="335" y="249" text-anchor="middle">{esc(data["x_label"])}{" (log scale)" if log else ""}</text></svg>'
        f'<div class="chart-legend">{"".join(legend)}</div>'
        '<details class="chart-data"><summary>Read the chart data</summary>'
        + table(["Series", data["x_label"], data["y_label"]], rows)
        + "</details></figure>"
    )


def _plan(data: dict) -> str:
    rows = []

    def walk(node, depth=0):
        rows.append(
            (
                "↳ " * depth + node["operator"],
                node["rows_in"],
                node["estimated_rows_out"] if node["estimated_rows_out"] is not None else "Not reported",
                node["rows_out"],
            )
        )
        for child in node["children"]:
            walk(child, depth + 1)

    walk(data["root"])
    out = f'<section data-query="{esc(data["query"])}"><p><strong>{esc(data["label"])}</strong></p>'
    out += "<p>Read the tree from its deepest input towards the result. Estimates precede execution; actual rows come from the profile.</p>"
    out += table(["Operator", "Rows in", "Estimated rows out", "Actual rows out"], rows)
    out += f"<p>Result rows: <strong>{number(data['result_rows'])}</strong>.</p>"
    out += "<details><summary>See the first result rows</summary>"
    out += table(data["preview"]["columns"], data["preview"]["rows"]) + "</details></section>"
    return out + "".join(_plan(v) for v in data.get("variants", []))


def worked_result(data: dict) -> str:
    kind = data["experiment"]
    title = data.get(
        "title",
        {
            "plan": "Follow the rows",
            "gather": "The cost of scattered reads",
            "pruning": "Which storage units can be skipped?",
            "branches": "The cost of a decision",
        }.get(kind, "Worked result"),
    )
    query = f' data-query="{esc(data["query"])}"' if data.get("query") else ""
    out = f'<section class="worked-result"{query} aria-label="{esc(title)}"><p class="result-kicker">Worked result · no execution needed</p><h3>{esc(title)}</h3>'
    if kind == "measure":
        out += f'<p>{esc(data["facts"])}</p><div class="result-cases">'
        maximum = max(c["measured"] for c in data["cases"]) or 1
        for case in data["cases"]:
            out += f'<section class="result-case"><h4>{esc(case["label"])}</h4><p>{esc(case["detail"])}</p>'
            out += f'<p class="result-value">{number(case["measured"])} <span>{esc(data["predict"]["label"])}</span></p>'
            out += f'<div class="result-bar" aria-hidden="true"><span style="width:{100 * case["measured"] / maximum:.3f}%"></span></div>'
            out += (
                table(
                    ["Counter", "Value"],
                    [(case["reference"]["label"], case["reference"]["value"]), *case["counters"]],
                )
                + "</section>"
            )
        out += "</div>"
        if data.get("chart"):
            out += chart(data["chart"])
    elif kind == "plan":
        out += _plan(data)
    elif kind == "gather":
        out += f"<p>Read the {esc(data['column'])} column in each access order. The model has {number(data['cache']['lines'])} cache lines of {number(data['cache']['line_bytes'])} bytes each.</p>"
        for item in data["gathers"]:
            out += f"<h4>{esc(item['fixture'])}</h4>"
            dots = "".join(
                f'<circle cx="{5 + 310 * i / max(1, len(item["pattern"]) - 1):.2f}" cy="{115 - 110 * line / max(1, data["column_lines"] - 1):.2f}" r="1.8"/>'
                for i, line in enumerate(item["pattern"])
            )
            out += (
                '<figure class="access-pattern"><svg viewBox="0 0 320 120" role="img" '
                f'aria-label="Sampled memory access pattern for {esc(item["fixture"])}">{dots}</svg>'
                f"<figcaption>Across: one read in every {number(item['pattern_every'])}, in date order. Up: the column’s cache line. "
                "A rising trace means nearby accesses; scattered dots mean jumping between lines.</figcaption></figure>"
            )
            out += table(
                ["Reads", "Hits", "Misses", "Bytes fetched"],
                [[item[k] for k in ("reads", "hits", "misses", "bytes_fetched")]],
            )
        out += "<p>A miss fetches a whole line. Reusing a line avoids that fetch; scattered access can evict a line before its next use.</p>"
    elif kind == "pruning":
        out += f"<p>Filter: {esc(' and '.join(data['filters']))}</p>"
        for file in data["files"]:
            out += f"<h4>{esc(file.get('label', file['fixture']))}</h4>"
            out += '<div class="unit-strip" aria-label="Storage units in file order">'
            out += (
                "".join(
                    f'<span class="{"unit-read" if u["read"] else "unit-skip"}" title="{esc(u["why"])}">{i + 1}<small>{"Read" if u["read"] else "Skip"}</small></span>'
                    for i, u in enumerate(file["units"])
                )
                + "</div>"
            )
            out += table(
                ["Units read", "Rows decoded", "Result rows", "Bytes read", "Requests"],
                [[file[k] for k in ("units_read", "rows_decoded", "rows_out", "bytes_read", "requests")]],
            )
            out += "<details><summary>Why each unit is read or skipped</summary>"
            out += (
                table(
                    [file["unit"].capitalize(), "Minimum", "Maximum", "Decision"],
                    [(i + 1, u["min_label"], u["max_label"], u["why"]) for i, u in enumerate(file["units"])],
                )
                + "</details>"
            )
    elif kind == "branches":
        out += table(
            ["Case", "Test", "Kernel", "Rows kept", "Branches", "Mispredictions"],
            [
                (c["label"], c["test"], c["kernel"], c["kept"], c["branches"], c["mispredictions"])
                for c in data["cases"]
            ],
        )
        out += chart(
            {
                "x_label": "Threshold",
                "y_label": "Mispredictions",
                "series": [
                    {"label": label, "points": [[p["threshold"], p[key]] for p in data["sweep"]]}
                    for label, key in [("With a branch", "with"), ("Without a branch", "without")]
                ],
            }
        )
    else:
        raise ValueError(f"No static reading view for experiment {kind!r}")
    return (
        out
        + f'<p class="result-source">Computed from the book’s fixtures with {esc(data["engine"])}. These are counts, not elapsed times. The surrounding text explains the model’s limits.</p></section>'
    )
