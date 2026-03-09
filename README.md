# OpenClaw Skill Risk Scanner

> **自动化评估 OpenClaw 生态技能包的安全风险，帮助企业 IT 决策者规避 AI Agent 供应链威胁。**

🔗 **Live Demo** → [jackart001.github.io/openclaw-risk-scanner](https://jackart001.github.io/openclaw-risk-scanner)

![自动更新](https://img.shields.io/badge/更新频率-每日-38bdf8)
![Python](https://img.shields.io/badge/Python-3.11-4ade80)
![Mistral](https://img.shields.io/badge/Mistral-AI分类-f97316)
![License](https://img.shields.io/badge/License-MIT-f59e0b)

---

## 背景

在实际使用 OpenClaw 的过程中，发现第三方技能包生态存在明显的信息不对称问题：

- ClawHub 上约 **13–20%** 的技能包存在安全隐患（数据来源：OpenClaw 社区安全报告 2026.3）
- 风险信息分散在 GitHub Issues、Discord 频道、中文社区三处，企业 IT 无法高效获取
- 现有工具缺乏**可解释的量化评分**，决策者只能凭直觉判断

本项目构建了一套基于规则引擎的自动化评估框架，每日运行，结果公开透明。

---
## 使用说明

**直接查看报告**
👉 [jackart001.github.io/openclaw-risk-scanner](https://jackart001.github.io/openclaw-risk-scanner)

报告每日自动更新，无需安装任何东西。

**自己部署（Fork 教程）**
🔲 完整 Fork 教程撰写中，敬请期待。
---
## 已实现

- ✅ 三维评分框架（安全可信度 · 维护健康度 · 社区信誉度）
- ✅ Mistral AI 自动识别真实 OpenClaw 技能包
- ✅ 每日自动扫描Github OpenClaw skills，每周自动发现新技能包
- ✅ GitHub Pages 免费托管，报告实时可访问

## 开发计划

- 🔲 报告支持按风险 / Star 数 / 发布时间排序
- 🔲 中英文双语报告
- 🔲 Fork 一键部署教程
- 🔲 扩展至其他 AI Agent 社区（LangChain / AutoGen）
- 🔲 将扫描器封装为 OpenClaw 原生技能包
- 🔲 关注包评级变化时飞书推送告警
---

## 快速上手

```bash
git clone https://github.com/your-username/openclaw-risk-scanner
cd openclaw-risk-scanner
pip install -r requirements.txt

# 扫描单个仓库
python main.py owner/repo-name

# 扫描列表
python main.py --list repos.txt
```

扫描完成后，`output/index.html` 即为可直接打开的报告。

---

## Methodology — 评分方法论

评分框架来源于对企业 IT 采购决策中三类核心顾虑的拆解：

### 三个核心问题

| 顾虑层次 | 核心问题 | 对应维度 |
|---|---|---|
| 第一层 | 会不会出安全事故？ | 安全可信度 Safety |
| 第二层 | 出了问题有没有人负责？ | 维护健康度 Maintenance |
| 第三层 | 会不会成为孤儿依赖？ | 社区信誉度 Reputation |

### 权重设计理由

安全维度权重 **50%**，而非三维均权。这来自金融风控的非对称损失逻辑——安全事故的代价远大于用了一个烂项目的沉默成本，因此不应平权。

### 维度一：安全可信度（50%）

| 评分项 | 扣分逻辑 | 最大扣分 |
|---|---|---|
| 权限声明 | README 未声明所需系统权限 | -30 |
| 危险系统调用 | 检测到 exec/subprocess/os.system 等，每次 -10 | -40 |
| 网络外发 | 无说明的 HTTP POST/Socket 调用，每次 -8 | -20 |
| 隐私数据访问 | 读取环境变量/文件/剪贴板，每次 -5 | -10 |

### 维度二：维护健康度（30%）

| 评分项 | 计算方式 | 满分 |
|---|---|---|
| 活跃度 | 90天内满分，线性衰减，>365天得0 | 40 |
| Issue 响应速度 | 平均关闭时长 <7天满分，>90天得0 | 30 |
| 版本规范 | 存在语义化版本号或 Release 记录 | 30 |

> **为什么维护健康度比社区信誉更重要？**
> Star 数可以刷，但 commit 历史和 Issue 响应时间造假成本极高，是更可信的信号。

### 维度三：社区信誉度（20%）

| 评分项 | 扣分逻辑 | 最大扣分 |
|---|---|---|
| 负面关键词 | Issue 中出现 security/malware/backdoor 等，每次 -15 | -50 |
| 账号创建时长 | <30天 -35，<90天 -15（防一次性账号） | -35 |
| 作者仓库数量 | <3个公开仓库 -15（背景单薄） | -15 |

> **为什么账号创建时长是指标？**
> 恶意技能包的典型模式是一次性账号快速上传，这是 AI Agent 生态供应链攻击的常见手法。

### 评级映射

| 分数区间 | 等级 | 建议 |
|---|---|---|
| 85–100 | ✅ SAFE | 推荐使用 |
| 65–84 | ⚠️ REVIEW | 建议人工复核后使用 |
| 40–64 | 🔶 CAUTION | 仅限受控环境测试 |
| 0–39 | ❌ DANGER | 禁止在生产环境使用 |

---

## 技术架构

```
GitHub Search API
    │
    └─ discovery.py      多关键词搜索候选仓库
         │
    Mistral AI           判断是否为真实 OpenClaw 技能包
         │
    repos.txt            通过审核的仓库清单（每周自动更新）
         │
    GitHub API
         ├─ fetch_repo()      基础信息 + 作者账号数据
         ├─ fetch_issues()    Issue 响应时长 + 负面词检测
         ├─ fetch_source()    下载源码，关键词扫描
         └─ fetch_readme()    权限声明检测
              │
         scorer.py            规则引擎评分（确定性，可解释）
              │
         reporter.py          生成静态 HTML 报告
              │
         GitHub Pages         每日自动发布
```

**关键设计决策**：发现阶段用 Mistral AI 做语义分类（判断"是不是真正的 OpenClaw 技能包"），
评分阶段用规则引擎（保证结果确定性和可解释性）。两个阶段各用最合适的工具，互不干扰。

---

## 作者

**刘俊杰 Liu Junjie**  
华威大学 信息系统管理与数字创新 MSc  
背景：AI 应用 · 金融风控 · 企业数字化

> 本项目的评分框架设计结合了金融行业风控的非对称损失逻辑与 GitHub 生态的数据可信度分析，欢迎 Issue 和 PR。

---
如果这个项目对你有帮助，点击右上角 ⭐ Star 是对我最大的鼓励！

## License
MIT
