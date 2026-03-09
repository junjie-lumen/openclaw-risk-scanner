"""
生成静态 HTML 报告
输出到 output/index.html，可直接用 GitHub Pages 托管
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LEVEL_COLOR = {
    "SAFE":    ("#22c55e", "#052e16"),
    "REVIEW":  ("#f59e0b", "#1c1100"),
    "CAUTION": ("#f97316", "#1a0a00"),
    "DANGER":  ("#ef4444", "#1a0000"),
}

LEVEL_BG = {
    "SAFE":    "#052e16",
    "REVIEW":  "#1c1100",
    "CAUTION": "#1a0a00",
    "DANGER":  "#1a0000",
}


def _row(result: dict) -> str:
    r = result
    color, bg = LEVEL_COLOR.get(r["level"], ("#94a3b8", "#0f172a"))
    flags_html = "".join(
        f'<li style="color:#94a3b8;font-size:11px;margin:3px 0">{f}</li>'
        for f in r["flags"]
    ) if r["flags"] else '<li style="color:#475569;font-size:11px">无风险项</li>'

    breakdown = r["breakdown"]
    bars = ""
    for dim, info in breakdown.items():
        dim_label = {"safety": "安全", "maintenance": "维护", "reputation": "信誉"}[dim]
        s = info["score"]
        bar_color = "#22c55e" if s >= 80 else "#f59e0b" if s >= 50 else "#ef4444"
        bars += f"""
        <div style="margin:4px 0">
          <span style="font-size:10px;color:#64748b;font-family:monospace;display:inline-block;width:40px">{dim_label}</span>
          <span style="display:inline-block;height:6px;width:{s}%;background:{bar_color};border-radius:3px;vertical-align:middle;max-width:120px"></span>
          <span style="font-size:10px;color:{bar_color};font-family:monospace;margin-left:6px">{s}</span>
          <span style="font-size:9px;color:#334155;margin-left:2px">({info['weight']})</span>
        </div>"""

    return f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-left:3px solid {color};
                border-radius:8px;padding:16px;margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
        <div>
          <div style="font-size:13px;font-weight:700;color:#e2e8f0;font-family:monospace">
            {r['owner']}/{r['repo']}
          </div>
          <div style="font-size:10px;color:#475569;margin-top:2px">{r['repo_url']}</div>
        </div>
        <div style="margin-left:auto;text-align:right">
          <div style="font-size:28px;font-weight:900;color:{color};font-family:monospace;line-height:1">{r['total']}</div>
          <div style="font-size:10px;color:{color};margin-top:2px">{r['label']}</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>{bars}</div>
        <div>
          <div style="font-size:10px;color:#475569;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px">检测到的风险项</div>
          <ul style="margin:0;padding-left:14px">{flags_html}</ul>
        </div>
      </div>
    </div>"""


def generate(results: list[dict], output_path: str = "output/index.html") -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(results)
    safe_count    = sum(1 for r in results if r["level"] == "SAFE")
    danger_count  = sum(1 for r in results if r["level"] in ("DANGER", "CAUTION"))

    rows_html = "".join(_row(r) for r in sorted(results, key=lambda x: x["total"]))

    summary_stats = f"""
    <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px 20px;text-align:center;min-width:100px">
        <div style="font-size:24px;font-weight:900;color:#e2e8f0;font-family:monospace">{total}</div>
        <div style="font-size:10px;color:#475569;margin-top:4px;text-transform:uppercase;letter-spacing:1px">扫描包数</div>
      </div>
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px 20px;text-align:center;min-width:100px">
        <div style="font-size:24px;font-weight:900;color:#22c55e;font-family:monospace">{safe_count}</div>
        <div style="font-size:10px;color:#475569;margin-top:4px;text-transform:uppercase;letter-spacing:1px">安全</div>
      </div>
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px 20px;text-align:center;min-width:100px">
        <div style="font-size:24px;font-weight:900;color:#ef4444;font-family:monospace">{danger_count}</div>
        <div style="font-size:10px;color:#475569;margin-top:4px;text-transform:uppercase;letter-spacing:1px">需警惕</div>
      </div>
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:14px 20px;text-align:center;min-width:180px;margin-left:auto">
        <div style="font-size:11px;color:#38bdf8;font-family:monospace">最近更新</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:4px;font-family:monospace">{now}</div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OpenClaw Skill Risk Scanner</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=Noto+Sans+SC:wght@400;600;700&display=swap');
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:#020817; color:#e2e8f0; font-family:'Noto Sans SC',sans-serif; padding:24px; }}
    a {{ color:#38bdf8; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <div style="max-width:860px;margin:0 auto">

    <div style="margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #1e293b">
      <div style="display:flex;align-items:baseline;gap:12px">
        <h1 style="font-size:20px;font-family:'IBM Plex Mono',monospace;font-weight:700;color:#38bdf8">
          OpenClaw Skill Risk Scanner
        </h1>
        <span style="font-size:11px;color:#475569;font-family:monospace">by Liu Junjie</span>
      </div>
      <p style="font-size:12px;color:#64748b;margin-top:8px;line-height:1.7">
        针对 OpenClaw 生态技能包的自动化安全评估工具。
        基于<strong style="color:#94a3b8">安全可信度（50%）· 维护健康度（30%）· 社区信誉度（20%）</strong>三维评分框架，
        帮助企业 IT 决策者在采购 AI Agent 技能包时规避供应链风险。
      </p>
    </div>

    {summary_stats}
    {rows_html}

    <div style="margin-top:28px;padding-top:16px;border-top:1px solid #1e293b;font-size:10px;color:#334155;font-family:monospace;text-align:center">
      数据来源：GitHub API · 评分方法论详见
      <a href="https://github.com/YOUR_USERNAME/openclaw-risk-scanner#methodology">README</a>
      · 每日 UTC 00:00 自动更新
    </div>
  </div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ 报告已生成：{output_path}")


def save_json(results: list[dict], path: str = "output/results.json") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ JSON 已保存：{path}")
