"""
OpenClaw Skill Risk Scorer
评分框架：三维九项，满分100分
"""

from datetime import datetime, timezone
import re


# ── 危险关键词库 ──────────────────────────────────────────────
DANGER_PATTERNS = [
    r"subprocess\.run", r"subprocess\.Popen", r"os\.system",
    r"os\.popen", r"exec\(", r"eval\(",
]

NETWORK_PATTERNS = [
    r"requests\.post", r"requests\.put", r"urllib\.request\.urlopen",
    r"socket\.connect", r"httpx\.post",
]

PRIVACY_PATTERNS = [
    r"os\.environ", r"open\(.+['\"]w['\"]",
    r"pyperclip", r"clipboard", r"glob\.glob",
]

NEGATIVE_ISSUE_KEYWORDS = [
    "malware", "security", "vulnerable", "vulnerability",
    "suspicious", "backdoor", "steal", "leak", "exploit",
    "unsafe", "dangerous", "credential",
]

PERMISSION_KEYWORDS = [
    "permission", "require", "access", "privilege",
    "需要权限", "权限说明", "系统访问",
]


# ── 工具函数 ──────────────────────────────────────────────────
def count_pattern_hits(text: str, patterns: list[str]) -> int:
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, text, re.IGNORECASE))
    return count


def days_since(dt_str: str) -> int:
    """ISO 8601 字符串 → 距今天数"""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


# ── 维度一：安全可信度 Safety（权重 50%）────────────────────
def score_safety(source_code: str, readme: str) -> dict:
    score = 100
    flags = []

    # 1-a 权限声明（满分40，无声明扣30）
    if not any(k in readme.lower() for k in PERMISSION_KEYWORDS):
        score -= 30
        flags.append("README 未声明所需权限")

    # 1-b 危险系统调用（每次命中扣10，最多扣40）
    danger_hits = count_pattern_hits(source_code, DANGER_PATTERNS)
    deduct = min(danger_hits * 10, 40)
    if danger_hits:
        score -= deduct
        flags.append(f"检测到 {danger_hits} 处危险系统调用（exec/subprocess等）")

    # 1-c 网络外发（每次命中扣8，最多扣20）
    net_hits = count_pattern_hits(source_code, NETWORK_PATTERNS)
    deduct = min(net_hits * 8, 20)
    if net_hits and "privacy" not in readme.lower():
        score -= deduct
        flags.append(f"检测到 {net_hits} 处网络外发调用且 README 无说明")

    # 1-d 隐私数据访问（每次命中扣5，最多扣10）
    priv_hits = count_pattern_hits(source_code, PRIVACY_PATTERNS)
    deduct = min(priv_hits * 5, 10)
    if priv_hits:
        score -= deduct
        flags.append(f"检测到 {priv_hits} 处环境变量/文件/剪贴板访问")

    return {"score": max(score, 0), "flags": flags}


# ── 维度二：维护健康度 Maintenance（权重 30%）───────────────
def score_maintenance(repo: dict, issues: list[dict]) -> dict:
    score = 0
    flags = []

    # 2-a 活跃度（满分40，90天内满分，线性递减，>365天得0）
    days = days_since(repo.get("pushed_at", repo["created_at"]))
    activity = max(0.0, 40 * (1 - days / 365))
    score += activity
    if days > 180:
        flags.append(f"最近一次提交距今 {days} 天，维护活跃度低")

    # 2-b Issue 响应速度（满分30）
    close_times = []
    for issue in issues:
        if issue.get("closed_at") and issue.get("created_at"):
            d = days_since(issue["created_at"]) - days_since(issue["closed_at"])
            if d >= 0:
                close_times.append(d)

    if close_times:
        avg_days = sum(close_times) / len(close_times)
        response_score = max(0.0, 30 * (1 - avg_days / 90))
        score += response_score
        if avg_days > 30:
            flags.append(f"Issue 平均关闭时长 {avg_days:.0f} 天")
    else:
        score += 15  # 无 issue 记录，给中性分
        flags.append("无已关闭 Issue 记录，响应速度未知")

    # 2-c 版本规范（满分30）
    has_version = bool(
        repo.get("has_releases") or
        re.search(r"v?\d+\.\d+\.\d+", repo.get("description") or "")
    )
    if has_version:
        score += 30
    else:
        flags.append("未检测到语义化版本号或 Release 记录")

    return {"score": min(int(score), 100), "flags": flags}


# ── 维度三：社区信誉度 Reputation（权重 20%）────────────────
def score_reputation(repo: dict, issues_text: str) -> dict:
    score = 100
    flags = []

    # 3-a 负面关键词（每次命中扣15，最多扣50）
    neg_hits = sum(
        issues_text.lower().count(k) for k in NEGATIVE_ISSUE_KEYWORDS
    )
    deduct = min(neg_hits * 15, 50)
    if neg_hits:
        score -= deduct
        flags.append(f"Issue 中出现 {neg_hits} 次安全相关负面词汇")

    # 3-b 作者账号可信度
    owner = repo.get("owner", {})
    account_age = days_since(owner.get("created_at", repo["created_at"]))
    public_repos = owner.get("public_repos", 0)

    if account_age < 30:
        score -= 35
        flags.append(f"发布者账号创建仅 {account_age} 天（疑似一次性账号）")
    elif account_age < 90:
        score -= 15
        flags.append(f"发布者账号较新（{account_age} 天）")

    if public_repos < 3:
        score -= 15
        flags.append(f"发布者仅有 {public_repos} 个公开仓库，背景单薄")

    return {"score": max(score, 0), "flags": flags}


# ── 综合评分 ─────────────────────────────────────────────────
def compute_final_score(safety: dict, maintenance: dict, reputation: dict) -> dict:
    weighted = (
        safety["score"] * 0.50 +
        maintenance["score"] * 0.30 +
        reputation["score"] * 0.20
    )
    total = round(weighted)

    if total >= 85:
        level, label = "SAFE",    "✅ 推荐使用"
    elif total >= 65:
        level, label = "REVIEW",  "⚠️  建议人工复核后使用"
    elif total >= 40:
        level, label = "CAUTION", "🔶 仅限受控环境测试"
    else:
        level, label = "DANGER",  "❌ 禁止在生产环境使用"

    all_flags = safety["flags"] + maintenance["flags"] + reputation["flags"]

    return {
        "total": total,
        "level": level,
        "label": label,
        "breakdown": {
            "safety":      {"score": safety["score"],      "weight": "50%"},
            "maintenance": {"score": maintenance["score"], "weight": "30%"},
            "reputation":  {"score": reputation["score"],  "weight": "20%"},
        },
        "flags": all_flags,
    }
