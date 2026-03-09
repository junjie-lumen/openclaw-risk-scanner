"""
OpenClaw Skill Risk Scanner — 主入口
用法：
  python main.py owner/repo [owner/repo ...]
  python main.py --list repos.txt
"""

import sys
import argparse
from pathlib import Path

# 把 src 加入路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fetcher import fetch_repo, fetch_issues, fetch_source_code, fetch_readme, parse_repo_url
from scorer  import score_safety, score_maintenance, score_reputation, compute_final_score
from reporter import generate, save_json


def scan_one(slug: str) -> dict | None:
    try:
        owner, repo = parse_repo_url(slug)
        print(f"⏳ 扫描 {owner}/{repo} ...")

        repo_data  = fetch_repo(owner, repo)
        issues     = fetch_issues(owner, repo)
        source     = fetch_source_code(owner, repo)
        readme     = fetch_readme(owner, repo)
        issues_text = " ".join(
            (i.get("title", "") + " " + (i.get("body") or ""))
            for i in issues
        )

        safety      = score_safety(source, readme)
        maintenance = score_maintenance(repo_data, issues)
        reputation  = score_reputation(repo_data, issues_text)
        result      = compute_final_score(safety, maintenance, reputation)

        result.update({
            "owner":    owner,
            "repo":     repo,
            "repo_url": f"https://github.com/{owner}/{repo}",
            "stars":    repo_data.get("stargazers_count", 0),
            "description": repo_data.get("description", ""),
        })

        print(f"   {result['label']}  总分：{result['total']}")
        return result

    except Exception as e:
        print(f"   ❌ 失败：{e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Skill Risk Scanner")
    parser.add_argument("repos", nargs="*", help="仓库地址，如 owner/repo 或完整 GitHub URL")
    parser.add_argument("--list", "-l", help="从文件读取仓库列表（每行一个）")
    args = parser.parse_args()

    slugs = list(args.repos)
    if args.list:
        slugs += Path(args.list).read_text().strip().splitlines()

    if not slugs:
        # 默认扫描示例列表（用于 GitHub Actions 每日自动运行）
        default_list = Path("repos.txt")
        if default_list.exists():
            slugs = default_list.read_text().strip().splitlines()
        else:
            print("请提供仓库地址，或创建 repos.txt 文件")
            sys.exit(1)

    results = []
    for slug in slugs:
        slug = slug.strip()
        if slug and not slug.startswith("#"):
            r = scan_one(slug)
            if r:
                results.append(r)

    if results:
        generate(results)
        save_json(results)
        print(f"\n🎉 完成！共扫描 {len(results)} 个包，报告：output/index.html")
    else:
        print("没有成功扫描任何仓库")
        sys.exit(1)


if __name__ == "__main__":
    main()
