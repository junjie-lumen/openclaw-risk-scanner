"""
自动发现模块
1. GitHub Search API 搜索候选仓库
2. Mistral 判断是否为真实 OpenClaw 技能包
3. 写入 repos.txt 供主扫描流程使用
"""

import os
import json
import time
import requests
from pathlib import Path

GITHUB_BASE = "https://api.github.com"
MISTRAL_API = "https://api.mistral.ai/v1/chat/completions"

# 搜索关键词组合，多撒网
SEARCH_QUERIES = [
    "topic:openclaw-skill",
    "topic:openclaw",
    "openclaw skill in:readme",
    "openclaw plugin in:readme",
    "openclaw-skill in:name",
]


# ── GitHub 搜索 ───────────────────────────────────────────────
def _gh_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def search_candidates(max_per_query: int = 30) -> list[dict]:
    """用多个关键词搜索候选仓库，去重后返回"""
    seen = set()
    candidates = []

    for query in SEARCH_QUERIES:
        url = f"{GITHUB_BASE}/search/repositories"
        params = {
            "q": query,
            "sort": "updated",
            "per_page": max_per_query,
        }
        try:
            r = requests.get(url, headers=_gh_headers(), params=params, timeout=10)
            if not r.ok:
                print(f"  搜索失败 [{query}]: {r.status_code}")
                continue

            items = r.json().get("items", [])
            for item in items:
                full_name = item["full_name"]
                if full_name not in seen:
                    seen.add(full_name)
                    candidates.append({
                        "full_name":   full_name,
                        "description": item.get("description") or "",
                        "stars":       item.get("stargazers_count", 0),
                        "updated_at":  item.get("updated_at", ""),
                        "html_url":    item.get("html_url", ""),
                        "topics":      item.get("topics", []),
                    })

            # GitHub Search API 有速率限制，礼貌等待
            time.sleep(1.5)

        except Exception as e:
            print(f"  搜索异常 [{query}]: {e}")

    print(f"发现 {len(candidates)} 个候选仓库（去重后）")
    return candidates


# ── Mistral 审核 ─────────────────────────────────────────────
def _mistral_headers() -> dict:
    token = os.environ.get("MISTRAL_API_KEY", "")
    if not token:
        raise EnvironmentError("缺少环境变量 MISTRAL_API_KEY")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


SYSTEM_PROMPT = """你是一个代码仓库分类专家，专门判断 GitHub 仓库是否为 OpenClaw AI Agent 框架的技能包（skill/plugin）。

OpenClaw 技能包的典型特征：
- README 或描述中提到 OpenClaw、claw-skill、agent skill
- 仓库名称包含 skill、plugin、agent、claw 等词
- 代码结构符合 OpenClaw 技能包规范（manifest.json、skill.py 等）
- Topics 中含有 openclaw、openclaw-skill、ai-agent

你必须只返回 JSON，格式如下，不要输出任何其他内容：
{"is_openclaw_skill": true/false, "confidence": "high/medium/low", "reason": "一句话理由"}"""


def classify_with_mistral(repo: dict, readme_snippet: str = "") -> dict:
    """
    让 Mistral 判断一个仓库是否为真实的 OpenClaw 技能包
    返回: {"is_openclaw_skill": bool, "confidence": str, "reason": str}
    """
    user_content = f"""仓库名：{repo['full_name']}
描述：{repo['description']}
Topics：{', '.join(repo['topics']) or '无'}
README 片段：{readme_snippet[:800] if readme_snippet else '无'}

请判断这是否为 OpenClaw 技能包。"""

    payload = {
        "model": "mistral-small-latest",   # 免费额度最大的型号
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.1,                 # 低温，保证输出稳定
        "max_tokens": 120,
    }

    try:
        r = requests.post(
            MISTRAL_API,
            headers=_mistral_headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()

        # 清理可能的 markdown 代码块
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        return result

    except json.JSONDecodeError:
        return {"is_openclaw_skill": False, "confidence": "low", "reason": "Mistral 返回格式异常"}
    except Exception as e:
        return {"is_openclaw_skill": False, "confidence": "low", "reason": str(e)}


# ── 拉取 README 片段（轻量版，不下载整个 zip）────────────────
def fetch_readme_snippet(full_name: str) -> str:
    import base64
    url = f"{GITHUB_BASE}/repos/{full_name}/readme"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=8)
        if not r.ok:
            return ""
        content = r.json().get("content", "")
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        return decoded[:1000]               # 只取前1000字符，省 token
    except Exception:
        return ""


# ── 主流程 ────────────────────────────────────────────────────
def discover_and_classify(
    output_file: str = "repos.txt",
    min_confidence: str = "medium",         # low / medium / high
    dry_run: bool = False,
) -> list[str]:
    """
    完整发现流程：搜索 → Mistral 分类 → 写入 repos.txt
    返回通过审核的仓库列表
    """
    print("=" * 50)
    print("🔍 Step 1: GitHub 搜索候选仓库")
    candidates = search_candidates()

    print(f"\n🤖 Step 2: Mistral 逐一审核（共 {len(candidates)} 个）")
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    min_rank = confidence_rank.get(min_confidence, 2)

    approved = []
    rejected = []

    for i, repo in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] {repo['full_name']} ...", end=" ")

        readme = fetch_readme_snippet(repo["full_name"])
        result = classify_with_mistral(repo, readme)

        is_skill  = result.get("is_openclaw_skill", False)
        conf      = result.get("confidence", "low")
        reason    = result.get("reason", "")
        conf_rank = confidence_rank.get(conf, 1)

        if is_skill and conf_rank >= min_rank:
            approved.append(repo["full_name"])
            print(f"✅ {conf} | {reason}")
        else:
            rejected.append(repo["full_name"])
            print(f"❌ {conf} | {reason}")

        # 礼貌等待，避免触发 Mistral 速率限制
        time.sleep(0.8)

    print(f"\n📊 结果：{len(approved)} 个通过，{len(rejected)} 个排除")

    if not dry_run and approved:
        _merge_into_repos_txt(approved, output_file)

    return approved


def _merge_into_repos_txt(new_repos: list[str], path: str) -> None:
    """把新发现的仓库合并进 repos.txt，避免重复"""
    existing = set()
    p = Path(path)

    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                existing.add(line)

    added = [r for r in new_repos if r not in existing]

    if not added:
        print("repos.txt 无需更新，所有发现的仓库已存在")
        return

    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n# 自动发现 — {__import__('datetime').date.today()}\n")
        for repo in added:
            f.write(f"{repo}\n")

    print(f"✅ 已将 {len(added)} 个新仓库写入 {path}")


# ── 单独运行入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="自动发现 OpenClaw 技能包")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写入 repos.txt")
    parser.add_argument("--min-confidence", default="medium", choices=["low", "medium", "high"])
    args = parser.parse_args()

    discover_and_classify(
        min_confidence=args.min_confidence,
        dry_run=args.dry_run,
    )
