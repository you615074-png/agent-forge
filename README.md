# AgentForge — 多 Agent 协作调度平台 v0.2

> 本地 CLI Agent 智能分发调度 | 单任务 + 4 阶段流水线 | 零依赖框架

---

## 是什么

把你在本地跑的 4 个 CLI Agent 串成一个智能调度系统。

```
forge "用 React 写一个计算器"
        │
        ▼
┌──────────────────────────────────────────────┐
│              AgentForge                       │
│                                              │
│  Stage 1: coding  → opencode  (DeepSeek)     │
│  Stage 2: review  → claudecode (GLM)         │
│  Stage 3: bugfix  → codex     (GPT)          │
│  Stage 4: testing → agy       (Gemini)       │
│                                              │
│  共享工作目录     上下文自动传递     归档存档   │
└──────────────────────────────────────────────┘
```

**不是让 Agent 互相聊天**，而是任务自动路由 → Agent 接力干活 → 汇总结果。

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/you615074-png/agent-forge.git
cd agent-forge

# 2. 安装唯一依赖
pip install pyyaml

# 3. 一行开干
py forge.py --mock "用 React 写一个计算器"    # mock 先试
py forge.py "用 React 写一个计算器"            # 真实执行
```

---

## 使用

### `forge` 智能启动器（推荐）

```bash
forge "build a login page"          # 走流水线（默认）
forge -s "fix the broken middleware" # 强制单任务
forge --mock "test"                 # 模拟模式
forge                                # 交互 REPL
```

### 交互 REPL

```bash
forge> build a calculator           # 流水线
forge> s fix the auth bug           # 单任务
forge> mock on                      # 切 mock
forge> quit
```

### 原始 CLI（仍可用）

```bash
# 流水线模式
python orchestrator.py --pipeline full_dev_cycle "your task"

# 单任务模式（v0.1 兼容）
python orchestrator.py "your task"
```

---

## Agent 军团

| Agent | 模型 | 角色 | 核心能力 |
|---|---|---|---|
| opencode | DeepSeek | 主力编码 + 全栈开发 | coding 0.95 / architecture 0.90 |
| claudecode | GLM | 代码审查 + 技术分析 | review 0.95 / reasoning 0.92 |
| codex | GPT | Bug 修复（配额保护） | debugging 0.92 / quick_fix 0.95 |
| agy | Gemini | 测试编写 + 质量验证 | testing 0.95 / verification 0.95 |

**GPT 配额保护**：codex 仅在 bugfix 类型胜出，其他任务类型不会匹配到它。

---

## 流水线设计

```
coding (DeepSeek)  ──→  review (GLM)  ──→  bugfix (GPT)  ──→  testing (Gemini)
                                          ↑                    │
                                    仅当审查发现问题时    共享工作目录中接力
```

每个阶段产出的文件对后续阶段可见，上下文通过 prompt 模板自动传递。

---

## 文件结构

```
agent-forge/
├── forge.py              # 智能启动器 + 交互 REPL
├── forge.bat             # Windows 命令行包装
├── orchestrator.py       # 主入口（双路径调度）
├── pipeline.py           # 流水线执行引擎 (v0.2)
├── classifier.py         # 关键词分类器
├── matcher.py            # 能力加权匹配引擎
├── executor.py           # CLI 执行器 + 会话管理
├── forge.yaml            # 全局配置（Agent/规则/权重/流水线）
└── sessions/             # 每次任务的完整存档
    └── pipeline-20260522-190000-a1b2c3d4/
        ├── _stage_coding_prompt.txt
        ├── _stage_coding_output.txt
        ├── _stage_review_prompt.txt
        ├── ...
        ├── pipeline_result.json
        └── src/           # Agent 产出的实际代码
```

---

## 配置

所有配置在 `forge.yaml` 中，不需要改代码：

```yaml
# 添加新 Agent
agents:
  my_new_agent:
    cli: "my_cli_command"
    capabilities:
      coding: 0.80
      review: 0.60

# 添加新流水线
pipelines:
  my_pipeline:
    stages:
      - id: step1
        type: coding
        prompt: "{original_task}"
      - id: step2
        type: review
        prompt: "审查: {all_files}"
```

---

## 设计原则

1. **调度器是死程序，不是 Agent** — 关键词 + 加权匹配，不做 AI 决策
2. **每次调用是新会话** — `subprocess.run([cli, task])`，用完即走
3. **成果在磁盘上** — 所有 Agent 共享工作目录，代码产出直接可见
4. **流水线阶段跳过分类器** — 阶段类型已在 YAML 声明，不走路由避免误判
5. **失败不阻断** — 任一阶段失败继续后续，最终汇总标状态

---

## 路线图

| 版本 | 功能 | 状态 |
|---|---|---|
| v0.1 | 单任务分发（分类+匹配+执行） | DONE |
| v0.2 | 流水线接力 + forge 启动器 + runner-up 降级 | DONE |
| v0.3 | 多方案对比（同任务发给所有 Agent） | TODO |
| v0.4 | 上下文存档 + 历史回溯 + 断点恢复 | TODO |
| v0.5 | 自我进化权重（根据成功率调整） | TODO |

---

## License

MIT
