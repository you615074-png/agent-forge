# 🎯 AgentForge — 多 Agent 协作调度平台 v0.1

> 本地 CLI Agent 自动分发调度 | Python 脚本 | 零依赖框架

---

## 是什么

把你在本地跑的 4 个 CLI Agent（opencode / claudecode / codex / agy）串成一个智能分发系统。

**不是让 Agent 互相聊天**，而是：你下达一个任务 → AgentForge 自动判断该谁干 → 调那个 Agent 干活 → 汇报结果。

```
你: "帮我写一个用户登录接口"
                     │
                     ▼
         ┌─────────────────────┐
         │    AgentForge        │
         │                     │
         │ ① 分类: 编码开发     │
         │ ② 匹配: opencode    │
         │ ③ 执行: 调 CLI      │
         │ ④ 汇总: 结果+产出   │
         └─────────────────────┘
                     │
         ┌───────────┘
         ▼
    opencode "帮我写一个用户登录接口"
         │
         ▼
    ✅ 完成 | 3.2s | 产出: auth/login.ts
```

---

## 安装

### 前置条件

- **Python 3.8+**
- 本地已安装的 CLI Agent（至少一个）：
  - [opencode](https://github.com/sst/opencode) — 全栈开发
  - [claude code](https://docs.anthropic.com/en/docs/claude-code) — 代码审查
  - [codex](https://github.com/openai/codex) — Bug 修复
  - [agy](https://github.com/nickcernis/agy) — 测试编写

### 安装步骤

```bash
# 1. 把 agent-forge 放到你想放的位置
git clone <your-repo> agent-forge
cd agent-forge

# 2. 安装 PyYAML（唯一依赖）
pip install pyyaml

# 3. 试跑
python orchestrator.py --mock "帮我写一个JWT认证中间件"
```

---

## 使用

### 单任务分发

```bash
python orchestrator.py "你的任务描述"
```

### 模拟模式（不真实调 Agent，测试用）

```bash
python orchestrator.py --mock "review 一下这段代码"
```

---

## 支持的 7 种任务类型

| 类型 | 说这个它就会识别 |
|:---|:---|
| 🔨 编码开发 | 写/开发/实现/搭建 + 接口/模块/项目 |
| 🔍 代码审查 | 审查/review/检查/有什么问题 |
| 🐛 Bug修复 | 修复/改/bug/报错/异常/解决 |
| 🧪 测试编写 | 测试/test/用例/验证/单元测试 |
| 🧠 技术分析 | 分析/解释/原理/对比/选型 |
| ♻️ 重构优化 | 重构/优化/改进/提升 |
| 📄 文档编写 | 文档/注释/readme/说明 |

---

## Agent 军团

| Agent | 擅长 | 能力 |
|:---|:---|:---|
| **opencode** | 编码开发、项目搭建 | 编码 0.90 / 架构 0.85 |
| **claudecode** | 代码审查、逻辑分析 | 审查 0.95 / 推理 0.90 |
| **codex** | Bug修复、快速生成 | 修复 0.95 / 调试 0.90 |
| **agy** | 测试编写、质量验证 | 测试 0.90 / 验证 0.90 |

---

## 文件结构

```
agent-forge/
├── orchestrator.py      # 主入口（你运行这个）
├── classifier.py        # 任务分类器
├── matcher.py           # 能力匹配引擎
├── executor.py          # CLI 执行器
├── forge.yaml           # 配置文件（改这个不改代码）
├── README.md            # 本文档
└── sessions/            # 每次任务的完整存档
    └── task-20260522-190000-a1b2c3d4/
        ├── prompt.txt           # 发给 Agent 的完整 prompt
        ├── opencode_output.txt  # Agent 输出
        └── result.json          # 结构化结果
```

---

## 配置

所有配置在 `forge.yaml` 中，无需改代码：

```yaml
# 添加新 Agent
agents:
  my_new_agent:
    cli: "my_cli_command"        # 终端命令
    capabilities:
      coding: 0.80               # 能力评分 0-1
      review: 0.60
      ...

# 添加新分类
classifier:
  rules:
    - type: my_task_type
      keywords: ["我的关键词1", "关键词2"]
```

---

## 路线图

| 版本 | 功能 | 状态 |
|:---:|------|:---:|
| **v0.1** | 单任务分发（分类+匹配+执行） | ✅ 当前 |
| v0.2 | 流水线接力（编码→审查→修复→测试） | 🔜 |
| v0.3 | 多方案对比（同任务发给所有 Agent） | 📋 |
| v0.4 | 上下文存档 + 历史回溯 | 📋 |
| v0.5 | 自我进化权重（根据成功率调整） | 📋 |

---

## 设计原则

1. **Orchestrator 是固定程序，不是 Agent** — 调度逻辑不需要 AI，关键词+权重就够了
2. **每次调 Agent 是新会话，不是持续对话** — `subprocess.run(["opencode", task])`，用完即走
3. **成果在磁盘上，不在 stdout 里** — Agent 把产出发到 stdout，但代码写在工作目录的磁盘文件里
4. **你能看懂每一行** — 三个模块加起来不到 300 行 Python，没框架、没魔法

---

## License

MIT
