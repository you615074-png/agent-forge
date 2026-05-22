#!/usr/bin/env python3
"""
AgentForge v0.1 — 多 Agent 调度平台
单任务分类 → 能力匹配 → 执行

用法:
  python orchestrator.py "帮我写一个用户登录接口"
  python orchestrator.py --mock "review 这段代码"    # 模拟模式，不调真实 Agent
"""

import sys
import os
import json
import yaml
from datetime import datetime

# 导入子模块
from classifier import classify
from matcher import match
from executor import execute
from pipeline import run_pipeline

# ── 加载配置 ──
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "forge.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 主流程 ──

def dispatch(task: str, mock: bool = False):
    """
    完整调度流程: 分类 → 匹配 → 执行 → 汇总
    """
    config = load_config()
    agents = config["agents"]
    classifier_rules = config["classifier"]["rules"]
    fallback = config["classifier"].get("fallback", "coding")
    match_weights = config["match_weights"]
    exec_config = config["executor"]

    print("=" * 60)
    print("  AgentForge v0.1 -- Multi-Agent Orchestrator")
    print("=" * 60)
    print()
    print(f"Task: {task[:100]}")
    print()

    # Step 1: 分类
    task_type, meta = classify(task, classifier_rules, fallback)
    type_names = {
        "coding": "[CODE] 编码开发",
        "review": "[REVIEW] 代码审查",
        "bugfix": "[BUGFIX] Bug修复",
        "testing": "[TEST] 测试编写",
        "analysis": "[ANALYZE] 技术分析",
        "refactor": "[REFACTOR] 重构优化",
        "documentation": "[DOCS] 文档编写",
    }
    type_label = type_names.get(task_type, f"? {task_type}")
    print(f"Classify: {type_label}")
    if meta.get("reason"):
        print(f"   (兜底: {meta['reason']})")
    print()

    # Step 2: 匹配
    match_result = match(task_type, agents, match_weights)
    if "error" in match_result:
        print(f"Match error: {match_result['error']}")
        return {"error": match_result["error"]}
    selected = match_result["selected"]
    score = match_result["score"]
    description = match_result["description"]

    print(f"Match:    {selected} (score: {score:.2f})")
    print(f"   {description}")
    print()

    # 显示所有 Agent 评分
    for s in match_result["all_scores"]:
        bar = "#" * int(s["score"] * 20)
        marker = " <-" if s["name"] == selected else ""
        print(f"   {s['name']:12s} {s['score']:.2f} {bar}{marker}")
    print()

    if mock:
        print("[MOCK] 模拟模式 — 不实际调用 Agent")
        print()
        return {
            "task": task,
            "task_type": task_type,
            "selected": selected,
            "score": score,
            "mock": True,
        }

    # Step 3: 执行
    agent = agents[selected]
    cli_command = agent["cli"]
    work_dir = os.path.join(
        os.path.dirname(__file__),
        exec_config.get("work_dir", "./sessions")
    )
    timeout = exec_config.get("timeout_seconds", 120)

    print(f"Exec:     {selected} ({cli_command})")
    print(f"   timeout: {timeout}s | work_dir: {work_dir}")
    print()

    result = execute(selected, cli_command, task, work_dir, timeout)

    # runner-up 降级：最佳 Agent 失败时自动换第二名
    if not result["success"] and match_result.get("runner_up"):
        runner = match_result["runner_up"]
        print(f"   [FALLBACK] {selected} failed, trying {runner}...")
        runner_agent = agents[runner]
        result = execute(runner, runner_agent["cli"], task, work_dir, timeout)
        if result["success"]:
            selected = runner

    # Step 4: 汇总
    print("-" * 60)
    print()

    if result["success"]:
        print(f"[OK] {selected} — {result['duration_ms']}ms")
    else:
        err_msg = result.get('error') or f"exit code {result.get('exit_code')}"
        print(f"[FAIL] {selected} — {err_msg}")
        print(f"   stderr: {result.get('stderr', '')[:200]}")

    if result["stdout"]:
        print()
        print("Output preview:")
        # 只显示前 500 字符
        preview = result["stdout"][:500]
        if len(result["stdout"]) > 500:
            preview += f"\n... ({len(result['stdout']) - 500} more chars)"
        print(preview)

    if result["produced_files"]:
        print()
        print("Files produced:")
        for f in result["produced_files"]:
            print(f"   {f['path']} ({f['size']} bytes)")

    print()
    print("-" * 60)
    print(f"Session:  {result['task_id']}")

    # 保存结果摘要
    summary_path = os.path.join(result["session_dir"], "result.json")
    summary = {
        "task": task,
        "task_type": task_type,
        "agent": selected,
        "score": score,
        "success": result["success"],
        "duration_ms": result["duration_ms"],
        "error": result.get("error"),
        "files": result["produced_files"],
        "timestamp": datetime.now().isoformat(),
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return result


# ── CLI 入口 ──

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python orchestrator.py \"你的任务描述\"")
        print("  python orchestrator.py --mock \"你的任务描述\"")
        print("  python orchestrator.py --pipeline <流水线名> \"你的任务描述\"")
        print("  python orchestrator.py --pipeline <流水线名> --mock \"你的任务描述\"")
        print()
        print("示例:")
        print("  python orchestrator.py \"帮我写一个JWT认证中间件\"")
        print("  python orchestrator.py --pipeline full_dev_cycle \"用React写一个计算器\"")
        print("  python orchestrator.py --pipeline full_dev_cycle --mock \"写一个计算器\"")
        sys.exit(1)

    mock_mode = "--mock" in sys.argv
    task_input = sys.argv[-1]

    # 流水线模式
    if "--pipeline" in sys.argv:
        pipeline_idx = sys.argv.index("--pipeline")
        try:
            pipeline_name = sys.argv[pipeline_idx + 1]
        except IndexError:
            print("Error: --pipeline requires a pipeline name")
            config = load_config()
            pipelines = config.get("pipelines", {})
            print(f"Available pipelines: {list(pipelines.keys())}")
            sys.exit(1)

        if pipeline_name.startswith("--"):
            print(f"Error: '{pipeline_name}' is not a valid pipeline name")
            config = load_config()
            pipelines = config.get("pipelines", {})
            print(f"Available pipelines: {list(pipelines.keys())}")
            sys.exit(1)

        config = load_config()
        run_pipeline(pipeline_name, task_input, config, mock=mock_mode)
        sys.exit(0)

    # 单任务模式
    dispatch(task_input, mock=mock_mode)
