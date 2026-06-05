# AgentForge v0.5 — Multi-Agent Pipeline Orchestrator

> Python 原生 · API Key 驱动 · 多 Agent 流水线 · 16 条斜杠命令 · Web GUI

---

## 这是什么

AgentForge 是一个 **多 Agent 协作的代码生成框架**。你填入 API Key，它调度多个 LLM Agent 按流水线接力完成任务：

```
$ python forge.py "用 Python 写个回文检测函数"

  Stage 1: coding  ──→ DeepSeek-Chat   write_file → palindrome.py
  Stage 2: review  ──→ DeepSeek-Chat   read_file  → 逐行审查，无 bug
  Stage 3: bugfix  ──→ (跳过 — 审查未发现问题)
  Stage 4: testing ──→ DeepSeek-Chat   bash pytest → 96 tests passed ✓
```

核心思路：**调度器是死的程序，不是 AI**。关键词分类 + 加权匹配 + 流水线接力，没有 AI 参与路由决策。

---

## 和 Claude Code / Codex CLI 的区别

这三个工具都让你在终端里用 AI 写代码，但定位不同：

| | AgentForge | Claude Code CLI | Codex CLI |
|---|---|---|---|
| **许可证** | MIT 开源 | 专有 (Proprietary) | Apache 2.0 开源 |
| **语言** | Python | TypeScript (Bun) | Rust |
| **安装** | `pip install` | `npm install -g` | `npm install -g` / `brew` |
| **运行方式** | API Key 直调 | API Key + CLI | API Key + CLI |
| **Agent 数量** | **4 个独立 Agent** (分工协作) | 1 个 + 子 Agent | 1 个 |
| **流水线** | ✅ 确定性 4 阶段接力 | ❌ 单 Agent 自主决策 | ❌ 单 Agent 自主决策 |
| **Provider** | **4 家** (Anthropic/OpenAI/Gemini/DeepSeek) | Anthropic 专用 | OpenAI 专用 (可配多后端) |
| **斜杠命令** | 16 条 | ~36 条 | ~6 条 |
| **Agent 工具** | 5 个 (read/write/bash/list/grep) | 20+ 个 | 10+ 个 |
| **Web GUI** | ✅ Flask 内建 | ✅ Web 版 (claude.ai/code) | ✅ Web 版 |
| **沙箱** | ❌ | ✅ macOS Seatbelt | ✅ 3 种模式 |
| **MCP 协议** | ❌ | ✅ | ✅ |
| **Hooks 系统** | ❌ 手动配置 | ✅ Pre/PostToolUse | ❌ |
| **上下文窗口** | API 限制 (4K-200K) | 200K-1M tokens | API 限制 |
| **Git 集成** | 可选自动提交 | ✅ diff/commit 内建 | ✅ 内建 |
| **CI/CD** | ❌ | ✅ 无头模式 | ✅ 内建支持 |
| **测试反馈循环** | ✅ 失败→修复→重测 | ✅ | ❌ |
| **适用场景** | 结构化多阶段开发任务 | 全栈开发 · 仓库级重构 | 安全优先 · CI 集成 |

**AgentForge 不做的事**（坦诚说）：
- 没有 Claude Code 那种沙箱隔离、MCP 生态、hooks 系统和子 Agent 调度
- 没有 Codex CLI 那种 Rust 级性能、三模式沙箱和原生 CI/CD 支持
- Agent 工具只有 5 个，比不上前两者 10-20+ 的工具集
- 没有 compact/rewind/resume 等会话管理

**AgentForge 独有的价值**：
- **多 Agent 流水线** — 不是让一个 AI 干所有事，而是编码→审查→修复→测试四道工序各司其职
- **Provider 自由搭配** — 可以用 DeepSeek 编码（便宜）+ Claude 审查（严谨），按预算灵活组合
- **零 CLI 依赖** — 只需 API Key，不需要装 `@anthropic/claude-code` 或 `@openai/codex`
- **Python 原生** — 如果你熟悉 Python 生态，二次开发非常方便
- **Web GUI 开箱即用** — 浏览器里操作流水线，不需要记命令

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/you615074-png/agent-forge.git
cd agent-forge

# 2. 安装依赖 (Python 3.9+)
pip install -r requirements.txt

# 3. 配置 API Key — 任选一种方式:

# 方式A: 环境变量 (推荐)
#   Windows PowerShell:  $env:DEEPSEEK_API_KEY = "sk-xxx"
#   Linux/macOS:         export DEEPSEEK_API_KEY=sk-xxx

# 方式B: 直接写在 forge.yaml (仅本地使用)
#   将每个 agent 的 api_key_env: DEEPSEEK_API_KEY
#   改为 api_key: sk-xxx

# 4. 修改 forge.yaml 使用 DeepSeek (便宜快速):
#   将每个 agent 的 provider: anthropic 改为 provider: deepseek
#   将每个 agent 的 model: claude-xxx 改为 model: deepseek-chat

# 5. 运行
python forge.py "用 Python 写个计算器"
```

**用 Anthropic (Claude) 的话**，只需设置 `ANTHROPIC_API_KEY`，forge.yaml 默认就是全 Claude 配置。

---

## 使用方式

### 命令行模式

```bash
python forge.py "写个 Flask TODO 应用"        # 流水线模式 (默认)
python forge.py -s "修一下登录 bug"            # 单 Agent 模式
python forge.py --mock "测试流水线结构"         # 空跑 (不调 API)
python forge.py                                # 交互 REPL
python forge.py --gui                          # 启动 Web 界面
python forge.py --serve 9090                   # 启动 REST API 服务
```

### 交互 REPL + 斜杠命令

```
forge> /help                    显示所有命令
forge> /doctor                  系统诊断 (Python版本/依赖/APIKey/工具)
forge> /init my-project         初始化项目 (forge.yaml + CLAUDE.md + .gitignore)
forge> /status                  当前状态 (mock模式/工作区/最近会话)
forge> /agents                  列出所有 Agent 及其能力
forge> /agents coder            查看 coder 的详细配置
forge> /pipeline full_dev_cycle 写个命令行工具   运行指定流水线
forge> /model                   查看当前模型配置
forge> /review                  对工作区代码进行审查
forge> /test -v                 运行测试
forge> /file src/main.py        查看文件 (带行号)
forge> /workspace               浏览工作区目录树
forge> /config show             查看完整配置
forge> /git status              Git 状态
forge> /git commit "修复了登录" 提交所有更改
forge> /memory                  查看 CLAUDE.md 项目知识
forge> /save                    保存当前会话摘要
forge> /clear                   清屏

forge> mock on                  开启空跑模式
forge> s 修复登录 bug            单 Agent 任务
forge> 写个计算器                流水线任务 (默认)
forge> quit                     退出
```

### Web 图形界面

```bash
python forge.py --gui
# 浏览器打开 http://127.0.0.1:8080
```

界面功能：
- 任务输入 + 流水线选择 + Mock 开关
- 实时流水线进度 (4 阶段徽章 + 进度条)
- 输出查看器 (成功/失败/警告高亮)
- 文件浏览器 (点击展开内容)
- 会话历史浏览器
- Agent 能力总览
- 配置查看器

### REST API

`python forge.py --serve 9090` 提供以下端点：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/config` | 获取配置 (密钥已脱敏) |
| GET | `/api/agents` | 列出所有 Agent |
| GET | `/api/pipelines` | 列出所有流水线 |
| POST | `/api/run` | 运行流水线 `{"task":"...", "pipeline":"full_dev_cycle"}` |
| GET | `/api/status` | 最近会话列表 |
| GET | `/api/status/<id>` | 会话状态和阶段结果 |
| GET | `/api/files/<id>` | 会话产生的文件列表 |
| GET | `/api/file/<id>/<path>` | 读取特定文件内容 |
| GET | `/api/sessions` | 磁盘上所有会话 |

---

## Agent 军团

默认配置为全 Anthropic，一个 Key 跑通全程：

| Agent | 默认模型 | 角色 | 核心能力 |
|---|---|---|---|
| coder | claude-opus-4-8 | 主力编码 | coding 0.95 / architecture 0.90 |
| reviewer | claude-sonnet-4-6 | 代码审查 | review 0.95 / reasoning 0.92 |
| bugfixer | claude-sonnet-4-6 | Bug 修复 (条件触发) | debugging 0.92 / quick_fix 0.95 |
| tester | claude-haiku-4-5 | 测试编写 | testing 0.95 / verification 0.95 |

### Agent 拥有的工具 (v0.4+)

每个 Agent 根据其角色获得不同的工具集：

| 工具 | coding | review | bugfix | testing |
|---|---|---|---|---|
| `read_file` — 读取文件 | ✓ | ✓ | ✓ | ✓ |
| `write_file` — 创建/覆写文件 | ✓ | | ✓ | ✓ |
| `list_files` — 列出目录 | ✓ | ✓ | ✓ | ✓ |
| `bash` — 执行命令 (pytest/npm/pip...) | ✓ | | ✓ | ✓ |
| `grep` — 代码搜索 | | ✓ | | |

### 支持的后端

| Provider | 可用模型 | 环境变量 |
|---|---|---|
| `anthropic` | claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5 | `ANTHROPIC_API_KEY` |
| `openai` | gpt-4.1, gpt-5, gpt-4o | `OPENAI_API_KEY` |
| `gemini` | gemini-2.5-pro, gemini-2.5-flash | `GEMINI_API_KEY` |
| `deepseek` | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |

每个 Agent 可以独立选择 Provider 和模型 —— 例如用 DeepSeek 做编码（便宜）、用 Claude 做审查（精准）：

```yaml
agents:
  coder:
    provider: deepseek
    model: deepseek-chat
    api_key_env: DEEPSEEK_API_KEY
  reviewer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
```

---

## 流水线设计

```
coding  ──→  review  ──→  bugfix  ──→  testing
(Opus)      (Sonnet)     (Sonnet)      (Haiku)
                           ↑ 条件触发
                      仅当 review 发现 __HAS_ISSUES__
                           │
                      测试反馈循环 (v0.5)
                      失败 → 自动修复 → 重测 (最多3轮)
```

### 测试反馈循环 (v0.5)

测试阶段如果检测到失败，自动进入修复循环：

```
Testing: 写测试 + 运行
    │
    ├── 全部通过 → ✅ 完成
    │
    └── 发现失败
         │
         ▼
     Bugfixer 修复代码
         │
         ▼
     重新运行测试
         │
         ├── 全部通过 → ✅ 完成
         │
         └── 仍然失败 → 重试 (最多 3 轮)
```

配置：
```yaml
test_loop:
  enabled: true
  max_iterations: 3
```

---

## 配置参考

全部配置在 `forge.yaml` 中，无需改代码：

```yaml
# API 全局设置
api:
  base_delay_ms: 500     # 重试基础延迟
  max_retries: 2         # 最大重试次数
  timeout_seconds: 300   # 请求超时

# Agent 定义 (可任意增减)
agents:
  coder:
    description: "主力编码"
    provider: anthropic           # 后端选择
    model: claude-opus-4-8        # 模型选择
    api_key_env: ANTHROPIC_API_KEY # 从环境变量读取 Key
    system_prompt: "You are an expert software engineer..."
    capabilities:                 # 能力分 (0-1)
      coding: 0.95
      architecture: 0.90
    tech_preference:              # 技术偏好
      - python
      - typescript

# 任务分类规则 (关键词匹配)
classifier:
  rules:
    - type: coding
      keywords: ["写", "开发", "实现", "build", "create", "implement"]
  fallback: coding

# 能力权重 (任务类型 → 所需能力的权重)
match_weights:
  coding:
    coding: 1.0
    architecture: 0.6

# Git 集成 (v0.5)
git:
  auto_commit: false
  commit_message_template: "AgentForge: {stage_id} — {task_summary}"

# 测试反馈循环 (v0.5)
test_loop:
  enabled: true
  max_iterations: 3

# 流水线定义 (可自定义)
pipelines:
  full_dev_cycle:
    description: "编码 → 审查 → 修复(条件) → 测试"
    stages:
      - id: coding
        type: coding
        prompt: '{original_task}'
      - id: review
        type: review
        prompt: |
          Review these files: {previous_files}
          If issues found, append __HAS_ISSUES__
        pass_files: true
      - id: bugfix
        type: bugfix
        condition:
          stage: review
          marker: "__HAS_ISSUES__"
      - id: testing
        type: testing
        prompt: |
          Write tests for: {all_files}
          Run tests to verify they pass.
        pass_files: true
```

---

## 项目结构

```
agent-forge/
├── forge.py              # 启动器 (REPL + CLI + GUI)
├── forge.yaml             # 全部配置
├── commands.py            # 斜杠命令系统 (v0.5)
├── server.py              # Web GUI + REST API (v0.5)
├── orchestrator.py        # 单任务调度
├── pipeline.py            # 流水线引擎 + 测试循环 (v0.5)
├── executor.py            # 双模式执行器 (CLI + API)
├── api_client.py          # LLM API 客户端 (4 家后端)
├── tools.py               # Agent 工具系统 (5 个工具)
├── workspace.py           # 工作区管理 + 文件内联
├── classifier.py          # 关键词任务分类
├── matcher.py             # 加权能力匹配
├── templates/
│   └── index.html         # Web 界面
├── static/
│   ├── style.css          # 暗色主题样式
│   └── app.js             # 前端逻辑
├── requirements.txt       # Python 依赖
├── .env.example           # API Key 模板
├── CLAUDE.md              # 项目知识文件
├── BUILD.md               # .exe 打包指南
└── sessions/              # 流水线输出归档
```

---

## 打包 .exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 一键构建
python forge.py --build-exe

# 输出: dist/AgentForge.exe (~20-30 MB, 自带 Python 运行时)
```

详细说明见 [BUILD.md](BUILD.md)。

---

## 设计原则

1. **调度器是死程序，不是 AI** — 关键词 + 加权匹配做路由，不靠 AI 决策
2. **每次调用是无状态的** — API 请求之间不保持会话
3. **产出落在磁盘上** — 所有 Agent 共享同一个工作目录
4. **流水线阶段跳过分类器** — 阶段类型在 YAML 里声明，不猜
5. **单阶段失败不阻塞** — 任何阶段失败，后续阶段继续执行
6. **工具优先于文本** — Agent 用 `write_file`/`read_file`/`bash` 而不是在 markdown 里输出代码
7. **Runner-up 降级** — 首选 Agent 失败自动换第二名

---

## 已验证

使用 DeepSeek API (`deepseek-chat`) 实测完整流水线：

```
[OK] coding:  23.2s → write_file → palindrome.py (docstring + type hints + doctest)
[OK] review:   9.7s → read_file  → "No bugs found" (正确跳过 bugfix)
[SKIP] bugfix                 → 审查通过，条件触发正确
[OK] testing: 63.4s → bash pytest → 96 tests collected, ALL PASSED ✓
```

---

## 版本历史

| 版本 | 内容 |
|---|---|
| v0.1 | 单任务调度 (分类 + 匹配 + 执行) |
| v0.2 | 流水线接力 + forge 启动器 + runner-up 降级 |
| v0.3 | API 驱动执行 (4 Provider: Anthropic/OpenAI/Gemini/DeepSeek) |
| v0.4 | Agent 工具系统 (read/write/bash/list/grep) + 文件内容内联 |
| v0.5 | 斜杠命令 (16 条) + Web GUI + 测试反馈循环 + Git 集成 + .exe 打包 |

---

## 路线图

| 版本 | 计划 |
|---|---|
| v0.6 | 多方案对比 (同一任务 → 所有 Agent → 评分选最优) |
| v0.7 | 会话管理 (compact / resume / rewind) |
| v0.8 | 交互式 diff 编辑 (逐文件审核/拒绝更改) |
| v0.9 | MCP 协议支持 |
| v1.0 | 插件系统 + 社区流水线市场 |

---

## 许可证

MIT License

---

## 参考

- Claude Code: [Anthropic 官方文档](https://docs.anthropic.com/en/docs/claude-code)
- Codex CLI: [github.com/openai/codex](https://github.com/openai/codex) (Apache 2.0)
- 本项目的比较分析基于 2025-2026 年公开信息
