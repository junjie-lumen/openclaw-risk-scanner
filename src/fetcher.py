"""
GitHub API 数据拉取模块
所有与 GitHub 的交互集中在这里，方便替换数据源
"""

import os
import io
import zipfile
import requests

BASE = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_repo(owner: str, repo: str) -> dict:
    """拉取仓库基础信息"""
    url = f"{BASE}/repos/{owner}/{repo}"
    r = requests.get(url, headers=_headers(), timeout=10)
    r.raise_for_status()
    data = r.json()

    # 补充：是否有 Release
    rel_url = f"{BASE}/repos/{owner}/{repo}/releases"
    rel_r = requests.get(rel_url, headers=_headers(), timeout=10)
    data["has_releases"] = bool(rel_r.ok and rel_r.json())

    # 补充：作者账号信息
    owner_url = f"{BASE}/users/{data['owner']['login']}"
    owner_r = requests.get(owner_url, headers=_headers(), timeout=10)
    if owner_r.ok:
        owner_data = owner_r.json()
        data["owner"]["created_at"]    = owner_data.get("created_at", "")
        data["owner"]["public_repos"]  = owner_data.get("public_repos", 0)

    return data


def fetch_issues(owner: str, repo: str, limit: int = 50) -> list[dict]:
    """拉取已关闭 Issue（用于计算响应速度 + 负面词检测）"""
    url = f"{BASE}/repos/{owner}/{repo}/issues"
    params = {"state": "closed", "per_page": limit}
    r = requests.get(url, headers=_headers(), params=params, timeout=10)
    if not r.ok:
        return []
    return r.json()


def fetch_source_code(owner: str, repo: str) -> str:
    """下载仓库 zip，提取所有 .py / .js / .ts 文件内容拼接返回"""
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
    r = requests.get(zip_url, headers=_headers(), timeout=30)
    if not r.ok:
        # 尝试 master 分支
        zip_url = zip_url.replace("main.zip", "master.zip")
        r = requests.get(zip_url, headers=_headers(), timeout=30)
    if not r.ok:
        return ""

    code_parts = []
    extensions = (".py", ".js", ".ts", ".sh", ".bash")
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            if name.endswith(extensions) and not name.startswith("__"):
                try:
                    code_parts.append(zf.read(name).decode("utf-8", errors="ignore"))
                except Exception:
                    pass

    return "\n".join(code_parts)


def fetch_readme(owner: str, repo: str) -> str:
    """拉取 README 原文"""
    url = f"{BASE}/repos/{owner}/{repo}/readme"
    r = requests.get(url, headers=_headers(), timeout=10)
    if not r.ok:
        return ""
    import base64
    content = r.json().get("content", "")
    try:
        return base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_repo_url(url_or_slug: str) -> tuple[str, str]:
    """
    支持多种输入格式：
      https://github.com/owner/repo
      github.com/owner/repo
      owner/repo
    """
    url_or_slug = url_or_slug.strip().rstrip("/")
    url_or_slug = url_or_slug.replace("https://", "").replace("http://", "")
    url_or_slug = url_or_slug.replace("github.com/", "")
    parts = url_or_slug.split("/")
    if len(parts) < 2:
        raise ValueError(f"无法解析仓库地址：{url_or_slug}")
    return parts[0], parts[1]
