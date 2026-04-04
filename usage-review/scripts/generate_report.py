#!/usr/bin/env python3
"""
Usage Review HTML 报告生成器

生成以「对比分析 + 改进建议」为核心的报告。
数据图表作为佐证穿插在各建议中，外部引用方便用户展开了解。

用法：
  python3 generate_report.py --data usage_data.json --insights insights.json --output report.html
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt(n: int) -> str:
    return f"{n:,}" if n >= 1000 else str(n)


def _parse_report_label(filename: str) -> str:
    """Extract display label from report filename like report_20260402_0943.html."""
    parts = filename.replace("report_", "").replace(".html", "")
    if "_" in parts and len(parts) >= 13:
        date_str, time_str = parts[:8], parts[9:13]
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}"
    date_str = parts[:8]
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def generate_index_html(output_path: str) -> None:
    """Scan data/ for report_*.html files, generate index.html with nav + iframe."""
    data_dir = Path(output_path).parent
    reports = []
    for f in sorted(data_dir.glob("report_*.html"), reverse=True):
        reports.append({"filename": f.name, "label": _parse_report_label(f.name)})

    # Include current report if not yet on disk (just written, glob may have it already)
    current_name = Path(output_path).name
    if not any(r["filename"] == current_name for r in reports):
        reports.insert(0, {"filename": current_name, "label": _parse_report_label(current_name)})

    nav_items = ""
    for r in reports:
        nav_items += (
            f'      <a class="nav-item" href="#{r["filename"]}" '
            f'data-file="{r["filename"]}">{r["label"]}</a>\n'
        )

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code Weekly Reports</title>
<style>
:root {{
  --bg:#0f1117; --s1:#1a1d27; --s2:#242836; --bd:#2d3148;
  --tx:#e4e4e7; --tm:#9ca3af; --ac:#6366f1; --al:#818cf8; --pu:#a855f7;
}}
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ display:flex; height:100vh; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:var(--bg); color:var(--tx) }}
nav {{ width:220px; min-width:220px; background:var(--s1); border-right:1px solid var(--bd); display:flex; flex-direction:column; height:100vh }}
.nav-hdr {{ padding:1.2rem 1rem .8rem; border-bottom:1px solid var(--bd) }}
.nav-hdr h1 {{ font-size:1rem; background:linear-gradient(135deg,var(--al),var(--pu)); -webkit-background-clip:text; -webkit-text-fill-color:transparent }}
.nav-hdr p {{ font-size:.72rem; color:var(--tm); margin-top:.2rem }}
.nav-list {{ flex:1; overflow-y:auto; padding:.5rem 0 }}
.nav-item {{ display:block; padding:.6rem 1rem; color:var(--tm); text-decoration:none; font-size:.85rem; border-left:3px solid transparent }}
.nav-item:hover {{ background:var(--s2); color:var(--tx) }}
.nav-item.active {{ color:var(--al); font-weight:600; background:rgba(99,102,241,.1); border-left-color:var(--al) }}
iframe {{ flex:1; border:none; height:100vh }}
</style>
</head>
<body>
  <nav>
    <div class="nav-hdr">
      <h1>Weekly Reports</h1>
      <p>{len(reports)} reports</p>
    </div>
    <div class="nav-list">
{nav_items}    </div>
  </nav>
  <iframe id="viewer" src=""></iframe>
  <script>
    const items = document.querySelectorAll('.nav-item');
    const viewer = document.getElementById('viewer');

    function load(filename) {{
      viewer.src = filename;
      items.forEach(function(el) {{
        el.classList.toggle('active', el.dataset.file === filename);
      }});
    }}

    items.forEach(function(el) {{
      el.addEventListener('click', function(e) {{
        e.preventDefault();
        var f = el.dataset.file;
        window.location.hash = f;
        load(f);
      }});
    }});

    // Load from hash or default to first report
    var hash = window.location.hash.slice(1);
    var target = hash || (items.length > 0 ? items[0].dataset.file : '');
    if (target) load(target);
  </script>
</body>
</html>"""

    index_path = data_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")


def generate_html(
    data: Dict[str, Any],
    insights: Dict[str, Any],
) -> str:
    meta = data.get("meta", {})
    history = data.get("history", {})
    tools = data.get("tools", {})
    costs = data.get("costs", {})
    compactions = data.get("compactions", {})

    period_start = meta.get("period_start", "")[:10]
    period_end = meta.get("period_end", "")[:10]
    days = meta.get("days", 7)

    # ── Chart data ──
    daily_activity = history.get("daily_activity", [])
    daily_labels = json.dumps([d[0][5:] for d in daily_activity])
    daily_values = json.dumps([d[1] for d in daily_activity])

    tool_dist = tools.get("tool_distribution", [])
    tool_labels = json.dumps([t[0] for t in tool_dist[:10]])
    tool_values = json.dumps([t[1] for t in tool_dist[:10]])

    top_projects = history.get("top_projects", [])

    daily_cost = costs.get("daily_cost", [])
    cost_labels = json.dumps([d[0][5:] for d in daily_cost])
    cost_values = json.dumps([round(d[1], 4) for d in daily_cost])

    slash_commands = history.get("slash_commands", [])

    # ── Insights ──
    patterns = insights.get("usage_patterns", {})
    strengths = patterns.get("strengths", [])
    improvements = patterns.get("improvements", [])
    recommendations = insights.get("recommendations", [])
    external_refs = insights.get("external_references", [])
    community_workflows = insights.get("community_workflows", [])

    # ── Build recommendations HTML ──
    recs_html = ""
    for rec in recommendations:
        pri = rec.get("priority", "medium").lower()
        badge_map = {
            "high": ('<span class="badge badge-high">HIGH</span>', "rec-high"),
            "medium": ('<span class="badge badge-medium">MEDIUM</span>', "rec-medium"),
            "low": ('<span class="badge badge-low">LOW</span>', "rec-low"),
        }
        badge, cls = badge_map.get(pri, ('<span class="badge">INFO</span>', ""))

        # comparison row
        your_val = rec.get("your_value", "")
        best_val = rec.get("best_practice", "")
        compare_html = ""
        if your_val or best_val:
            compare_html = f"""
                <div class="compare-row">
                    <div class="compare-you"><span class="compare-label">Your usage</span><span class="compare-val">{your_val}</span></div>
                    <div class="compare-arrow">→</div>
                    <div class="compare-best"><span class="compare-label">Best practice</span><span class="compare-val">{best_val}</span></div>
                </div>"""

        # playbook steps
        playbook = rec.get("playbook", {})
        steps_html = ""
        if playbook.get("steps"):
            steps_items = ""
            for i, st in enumerate(playbook["steps"], 1):
                example_html = ""
                if st.get("example"):
                    example_html = f'<pre class="pb-code">{st["example"]}</pre>'
                expect_html = ""
                if st.get("expect"):
                    expect_html = f'<div class="pb-expect"><strong>Expected:</strong> {st["expect"]}</div>'
                steps_items += f"""
                    <div class="pb-step">
                        <div class="pb-num">{i}</div>
                        <div class="pb-body">
                            <div class="pb-do">{st.get('do', '')}</div>
                            {example_html}
                            {expect_html}
                        </div>
                    </div>"""
            steps_html = f'<div class="pb-steps">{steps_items}</div>'

        ba_html = ""
        ba = playbook.get("before_after", {})
        if ba.get("before") or ba.get("after"):
            ba_html = f"""
                <div class="pb-ba">
                    <div class="pb-before"><div class="pb-ba-label">Before</div><pre class="pb-code">{ba.get('before','')}</pre></div>
                    <div class="pb-after"><div class="pb-ba-label">After</div><pre class="pb-code">{ba.get('after','')}</pre></div>
                </div>"""

        measure_html = ""
        if playbook.get("measure"):
            measure_html = f'<div class="pb-measure"><strong>Measure:</strong> {playbook["measure"]}</div>'

        playbook_html = ""
        if steps_html or ba_html or measure_html:
            playbook_html = f"""
            <details class="pb-details">
                <summary>Playbook: step-by-step</summary>
                {steps_html}{ba_html}{measure_html}
            </details>"""

        recs_html += f"""
        <div class="rec-card {cls}">
            <div class="rec-header">{badge}<h4>{rec.get('title', '')}</h4></div>
            <p class="rec-desc">{rec.get('description', '')}</p>
            {compare_html}
            {playbook_html}
        </div>"""

    # ── Strengths / improvements ──
    strengths_html = "".join(f'<li><span class="strength-icon">&#10003;</span> {s}</li>' for s in strengths)
    improvements_html = "".join(f'<li><span class="improve-icon">!</span> {i}</li>' for i in improvements)

    # ── Community workflows ──
    workflows_html = ""
    for wf in community_workflows:
        workflows_html += f"""
        <div class="workflow-card">
            <h4>{wf.get('title', '')}</h4>
            <p>{wf.get('description', '')}</p>
            <div class="workflow-steps">
                {"".join(f'<span class="step">{s}</span>' for s in wf.get('steps', []))}
            </div>
            <div class="workflow-source">— {wf.get('source', '')}</div>
        </div>"""

    # ── External references ──
    refs_html = ""
    for ref in external_refs:
        refs_html += f"""
        <div class="ref-card">
            <a href="{ref.get('url', '#')}" target="_blank" rel="noopener">{ref.get('title', '')}</a>
            <p>{ref.get('summary', '')}</p>
            <span class="ref-source">{ref.get('source', '')}</span>
        </div>"""

    # ── Slash commands table ──
    slash_html = "".join(
        f'<tr><td><code>{c[0]}</code></td><td>{c[1]}</td></tr>'
        for c in slash_commands[:10]
    )

    # ── Projects table ──
    max_proj = top_projects[0][1] if top_projects else 1
    proj_rows = "".join(
        f'<tr><td>{p[0]}</td><td>{p[1]}</td>'
        f'<td><div class="bar" style="width:{p[1]/max_proj*100:.0f}%"></div></td></tr>'
        for p in top_projects[:8]
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Code Weekly Review — {period_start} ~ {period_end}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root {{
  --bg:#0f1117; --s1:#1a1d27; --s2:#242836; --bd:#2d3148;
  --tx:#e4e4e7; --tm:#9ca3af; --ac:#6366f1; --al:#818cf8;
  --gn:#22c55e; --yl:#eab308; --rd:#ef4444; --bl:#3b82f6; --pu:#a855f7;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--tx);line-height:1.7;padding:2rem}}
.wrap{{max-width:960px;margin:0 auto}}
/* header */
.hdr{{text-align:center;padding:2.5rem 0 1.5rem;border-bottom:1px solid var(--bd);margin-bottom:2rem}}
.hdr h1{{font-size:1.8rem;background:linear-gradient(135deg,var(--al),var(--pu));-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.hdr .sub{{color:var(--tm);font-size:.9rem;margin-top:.4rem}}
/* section */
.sec{{background:var(--s1);border:1px solid var(--bd);border-radius:14px;padding:1.6rem;margin-bottom:1.5rem}}
.sec h2{{font-size:1.25rem;color:var(--al);margin-bottom:1rem;display:flex;align-items:center;gap:.5rem}}
.sec h2 .icon{{font-size:1.4rem}}
.sec h3{{font-size:1.05rem;margin:1.2rem 0 .6rem;color:var(--tx)}}
/* kpi */
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.8rem;margin-bottom:1.5rem}}
.kpi-c{{background:var(--s1);border:1px solid var(--bd);border-radius:10px;padding:1rem;text-align:center}}
.kpi-c .v{{font-size:1.6rem;font-weight:700;color:var(--al)}}
.kpi-c .l{{font-size:.78rem;color:var(--tm);margin-top:.2rem}}
/* two col */
.two{{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem}}
@media(max-width:768px){{.two{{grid-template-columns:1fr}}body{{padding:1rem}}}}
/* scorecard */
.scorecard{{display:flex;gap:1rem;margin:1rem 0}}
.score-item{{flex:1;text-align:center;padding:1rem;border-radius:10px;background:var(--s2)}}
.score-item .grade{{font-size:2rem;font-weight:800}}
.score-item .grade-a{{color:var(--gn)}}.score-item .grade-b{{color:var(--yl)}}.score-item .grade-c{{color:var(--rd)}}
.score-item .dim{{font-size:.8rem;color:var(--tm);margin-top:.3rem}}
/* strengths / improvements */
.si-list{{list-style:none;padding:0}}
.si-list li{{padding:.5rem .6rem;margin-bottom:.4rem;border-radius:8px;background:var(--s2);display:flex;align-items:flex-start;gap:.5rem;font-size:.9rem}}
.strength-icon{{color:var(--gn);font-weight:700;flex-shrink:0;width:1.2rem}}
.improve-icon{{color:var(--yl);font-weight:700;flex-shrink:0;width:1.2rem}}
/* rec cards */
.rec-card{{background:var(--s2);border-left:4px solid var(--bd);border-radius:0 10px 10px 0;padding:1.2rem;margin-bottom:1rem}}
.rec-high{{border-left-color:var(--rd)}}.rec-medium{{border-left-color:var(--yl)}}.rec-low{{border-left-color:var(--gn)}}
.rec-header{{display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem}}
.rec-header h4{{font-size:1rem}}
.rec-desc{{font-size:.9rem;color:var(--tm);margin-bottom:.6rem}}
.badge{{display:inline-block;padding:.1rem .45rem;border-radius:4px;font-size:.7rem;font-weight:700}}
.badge-high{{background:var(--rd);color:#fff}}.badge-medium{{background:var(--yl);color:#000}}.badge-low{{background:var(--gn);color:#fff}}
.compare-row{{display:flex;align-items:center;gap:.8rem;padding:.6rem;background:rgba(99,102,241,.06);border-radius:8px;margin:.5rem 0;font-size:.85rem}}
.compare-label{{display:block;font-size:.7rem;color:var(--tm);margin-bottom:.15rem}}
.compare-val{{font-weight:600}}
.compare-you .compare-val{{color:var(--yl)}}.compare-best .compare-val{{color:var(--gn)}}
.compare-arrow{{font-size:1.2rem;color:var(--tm)}}
.rec-action{{margin-top:.5rem;padding:.6rem .8rem;background:rgba(99,102,241,.1);border-radius:8px;font-size:.88rem}}
/* workflow cards */
.workflow-card{{background:var(--s2);border:1px solid var(--bd);border-radius:10px;padding:1.2rem;margin-bottom:.8rem}}
.workflow-card h4{{font-size:.95rem;color:var(--al);margin-bottom:.4rem}}
.workflow-card p{{font-size:.85rem;color:var(--tm);margin-bottom:.6rem}}
.workflow-steps{{display:flex;flex-wrap:wrap;gap:.4rem}}
.step{{background:var(--s1);border:1px solid var(--bd);padding:.25rem .6rem;border-radius:6px;font-size:.78rem;color:var(--tx)}}
.workflow-source{{font-size:.75rem;color:var(--tm);margin-top:.5rem;font-style:italic}}
/* ref cards */
.refs-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.8rem}}
.ref-card{{background:var(--s2);border:1px solid var(--bd);border-radius:10px;padding:1rem}}
.ref-card a{{color:var(--al);text-decoration:none;font-weight:600;font-size:.95rem}}
.ref-card a:hover{{text-decoration:underline}}
.ref-card p{{font-size:.82rem;color:var(--tm);margin:.3rem 0}}
.ref-source{{font-size:.72rem;color:var(--tm);opacity:.7}}
/* charts */
.chart-box{{position:relative;height:220px;margin:.8rem 0}}
/* tables */
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th,td{{padding:.5rem .6rem;text-align:left;border-bottom:1px solid var(--bd)}}
th{{color:var(--tm);font-weight:600}}
.bar{{height:7px;border-radius:4px;background:var(--ac)}}
/* ratio bar */
.ratio-bar{{display:flex;height:22px;border-radius:11px;overflow:hidden;margin:.5rem 0}}
.ratio-bar div{{display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:600;color:#fff;min-width:28px}}
/* footer */
.ftr{{text-align:center;padding:1.5rem 0;color:var(--tm);font-size:.78rem}}
/* collapsible */
details{{margin:.8rem 0}}
summary{{cursor:pointer;font-weight:600;color:var(--al);padding:.4rem 0;font-size:.95rem}}
summary:hover{{color:var(--pu)}}
/* playbook */
.pb-details{{margin:.6rem 0 0;background:var(--s1);border:1px solid var(--bd);border-radius:8px;padding:.2rem .8rem}}
.pb-details summary{{font-size:.88rem;padding:.5rem 0}}
.pb-details[open] summary{{border-bottom:1px solid var(--bd);margin-bottom:.5rem}}
.pb-steps{{padding:.4rem 0}}
.pb-step{{display:flex;gap:.7rem;margin-bottom:.8rem}}
.pb-num{{width:24px;height:24px;border-radius:50%;background:var(--ac);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0;margin-top:.1rem}}
.pb-body{{flex:1;min-width:0}}
.pb-do{{font-size:.88rem;margin-bottom:.3rem}}
.pb-code{{background:var(--bg);border:1px solid var(--bd);border-radius:6px;padding:.5rem .7rem;font-size:.8rem;font-family:'SF Mono',Monaco,Consolas,monospace;overflow-x:auto;white-space:pre;margin:.3rem 0;color:var(--gn)}}
.pb-expect{{font-size:.82rem;color:var(--tm);margin-top:.2rem}}
.pb-ba{{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin:.6rem 0}}
@media(max-width:600px){{.pb-ba{{grid-template-columns:1fr}}}}
.pb-ba-label{{font-size:.72rem;font-weight:700;text-transform:uppercase;margin-bottom:.2rem}}
.pb-before .pb-ba-label{{color:var(--rd)}}.pb-after .pb-ba-label{{color:var(--gn)}}
.pb-measure{{font-size:.85rem;padding:.5rem .7rem;background:rgba(99,102,241,.08);border-radius:6px;margin:.5rem 0 .3rem}}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
    <h1>Claude Code Weekly Review</h1>
    <p class="sub">{period_start} — {period_end} ({days} days) &middot; {fmt(history.get('total_inputs',0))} inputs across {history.get('unique_sessions',0)} sessions</p>
</div>

<!-- ═══ Section 1: Scorecard ═══ -->
<section class="sec">
    <h2><span class="icon">&#127919;</span> This Week at a Glance</h2>
    <div class="scorecard">
        <div class="score-item">
            <div class="grade {_tool_grade_class(tools)}">{_tool_grade(tools)}</div>
            <div class="dim">Tool Usage</div>
        </div>
        <div class="score-item">
            <div class="grade {_ctx_grade_class(history, compactions)}">{_ctx_grade(history, compactions)}</div>
            <div class="dim">Context Mgmt</div>
        </div>
        <div class="score-item">
            <div class="grade {_workflow_grade_class(history)}">{_workflow_grade(history)}</div>
            <div class="dim">Workflow</div>
        </div>
    </div>

    <div class="two">
        <div>
            <h3>What you're doing well</h3>
            <ul class="si-list">{strengths_html}</ul>
        </div>
        <div>
            <h3>Where to improve</h3>
            <ul class="si-list">{improvements_html}</ul>
        </div>
    </div>
</section>

<!-- ═══ Section 2: Recommendations ═══ -->
<section class="sec">
    <h2><span class="icon">&#128161;</span> Recommendations</h2>
    <p style="color:var(--tm);margin-bottom:1rem;font-size:.9rem">
        Based on your data vs community best practices. Sorted by impact.
    </p>
    {recs_html}
</section>

<!-- ═══ Section 3: Community Workflows ═══ -->
<section class="sec">
    <h2><span class="icon">&#127760;</span> How Others Use Claude Code</h2>
    <p style="color:var(--tm);margin-bottom:1rem;font-size:.9rem">
        Popular workflows from the community — see what resonates with your work.
    </p>
    {workflows_html}
</section>

<!-- ═══ Section 4: Your Data (collapsible detail) ═══ -->
<section class="sec">
    <h2><span class="icon">&#128202;</span> Your Usage Data</h2>

    <div class="kpi">
        <div class="kpi-c"><div class="v">{fmt(history.get('total_inputs',0))}</div><div class="l">Inputs</div></div>
        <div class="kpi-c"><div class="v">{history.get('unique_sessions',0)}</div><div class="l">Sessions</div></div>
        <div class="kpi-c"><div class="v">{history.get('avg_inputs_per_session',0)}</div><div class="l">Avg / Session</div></div>
        <div class="kpi-c"><div class="v">{fmt(tools.get('total_tool_calls',0))}</div><div class="l">Tool Calls</div></div>
        <div class="kpi-c"><div class="v">{compactions.get('total_compactions',0)}</div><div class="l">Compactions</div></div>
    </div>

    <details>
        <summary>Daily Activity</summary>
        <div class="chart-box"><canvas id="dailyChart"></canvas></div>
    </details>

    <details>
        <summary>Tool Distribution</summary>
        <div class="two">
            <div class="chart-box" style="height:240px"><canvas id="toolChart"></canvas></div>
            <div>
                <div class="ratio-bar">
                    <div style="width:{tools.get('bash_ratio',0)}%;background:var(--rd)" title="Bash">Bash {tools.get('bash_ratio',0)}%</div>
                    <div style="width:{tools.get('dedicated_tool_ratio',0)}%;background:var(--gn)" title="Dedicated">Dedicated {tools.get('dedicated_tool_ratio',0)}%</div>
                    <div style="width:{tools.get('agent_ratio',0)}%;background:var(--pu)" title="Agent">Agent {tools.get('agent_ratio',0)}%</div>
                    <div style="width:{max(100-tools.get('bash_ratio',0)-tools.get('dedicated_tool_ratio',0)-tools.get('agent_ratio',0),0)}%;background:var(--s2)" title="Other"></div>
                </div>
            </div>
        </div>
    </details>

    <details>
        <summary>Projects & Commands</summary>
        <div class="two">
            <div>
                <h3>Top Projects</h3>
                <table><tr><th>Project</th><th>Inputs</th><th></th></tr>{proj_rows}</table>
            </div>
            <div>
                <h3>Slash Commands</h3>
                <table><tr><th>Command</th><th>Count</th></tr>{slash_html}</table>
            </div>
        </div>
    </details>

    <details>
        <summary>Cost & Tokens</summary>
        <div class="kpi" style="margin-bottom:.8rem">
            <div class="kpi-c"><div class="v">${costs.get('total_cost_usd',0):.2f}</div><div class="l">Total Cost</div></div>
            <div class="kpi-c"><div class="v">{fmt(costs.get('total_input_tokens',0))}</div><div class="l">Input Tokens</div></div>
            <div class="kpi-c"><div class="v">{fmt(costs.get('total_output_tokens',0))}</div><div class="l">Output Tokens</div></div>
        </div>
        <div class="chart-box"><canvas id="costChart"></canvas></div>
    </details>
</section>

<!-- ═══ Section 5: Further Reading ═══ -->
<section class="sec">
    <h2><span class="icon">&#128214;</span> Further Reading</h2>
    <div class="refs-grid">{refs_html}</div>
</section>

<div class="ftr">Generated by Claude Code Usage Review &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
</div>

<script>
Chart.defaults.color='#9ca3af';
Chart.defaults.borderColor='#2d3148';
const grid={{color:'rgba(45,49,72,.5)'}};

new Chart(document.getElementById('dailyChart'),{{
  type:'bar',
  data:{{labels:{daily_labels},datasets:[{{data:{daily_values},backgroundColor:'rgba(99,102,241,.7)',borderRadius:4}}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,grid}},x:{{grid:{{display:false}}}}}}}}
}});

new Chart(document.getElementById('toolChart'),{{
  type:'doughnut',
  data:{{labels:{tool_labels},datasets:[{{data:{tool_values},backgroundColor:['#ef4444','#22c55e','#3b82f6','#a855f7','#eab308','#f97316','#06b6d4','#ec4899','#14b8a6','#8b5cf6'],borderWidth:0}}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'right',labels:{{boxWidth:10,padding:6,font:{{size:11}}}}}}}}}}
}});

new Chart(document.getElementById('costChart'),{{
  type:'line',
  data:{{labels:{cost_labels},datasets:[{{data:{cost_values},borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.1)',fill:true,tension:.3,pointRadius:3}}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,grid}},x:{{grid:{{display:false}}}}}}}}
}});
</script>
</body>
</html>"""
    return html


def _tool_grade(tools: Dict) -> str:
    bash = tools.get("bash_ratio", 0)
    if bash < 40:
        return "A"
    if bash < 55:
        return "B"
    return "C"

def _tool_grade_class(tools: Dict) -> str:
    return {"A": "grade-a", "B": "grade-b", "C": "grade-c"}[_tool_grade(tools)]

def _ctx_grade(history: Dict, comp: Dict) -> str:
    total_comp = comp.get("total_compactions", 0)
    sessions = history.get("unique_sessions", 1)
    ratio = total_comp / max(sessions, 1)
    if ratio < 0.5:
        return "A"
    if ratio < 1.0:
        return "B"
    return "C"

def _ctx_grade_class(history: Dict, comp: Dict) -> str:
    return {"A": "grade-a", "B": "grade-b", "C": "grade-c"}[_ctx_grade(history, comp)]

def _workflow_grade(history: Dict) -> str:
    cmds = dict(history.get("slash_commands", []))
    variety = len(cmds)
    if variety >= 8:
        return "A"
    if variety >= 4:
        return "B"
    return "C"

def _workflow_grade_class(history: Dict) -> str:
    return {"A": "grade-a", "B": "grade-b", "C": "grade-c"}[_workflow_grade(history)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Usage Review HTML 报告生成器")
    parser.add_argument("--data", required=True, help="collect_usage_data.py 输出的 JSON 文件")
    parser.add_argument("--insights", required=True, help="Claude 分析输出的 insights JSON 文件")
    parser.add_argument("--output", default="report.html", help="输出 HTML 文件路径")
    args = parser.parse_args()

    data = load_json(args.data)
    insights = load_json(args.insights)

    output_path = args.output

    html = generate_html(data, insights)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Regenerate index.html with current report list
    generate_index_html(output_path)

    print(f"报告已生成: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
