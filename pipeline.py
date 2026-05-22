"""
AgentForge — 流水线执行引擎 v0.2
支持多阶段任务接力执行，阶段间传递上下文
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any

from matcher import match
from executor import execute


# ── 类型显示名 ──
_TYPE_NAMES = {
    "coding": "[CODE] 编码开发",
    "review": "[REVIEW] 代码审查",
    "bugfix": "[BUGFIX] Bug修复",
    "testing": "[TEST] 测试编写",
    "analysis": "[ANALYZE] 技术分析",
    "refactor": "[REFACTOR] 重构优化",
    "documentation": "[DOCS] 文档编写",
}


def run_pipeline(pipeline_name: str, original_task: str,
                 config: dict, mock: bool = False) -> dict:
    """
    执行命名流水线。

    pipeline_name: forge.yaml pipelines 下定义的流水线名称
    original_task: 用户的原始任务描述
    config: 完整配置字典 (由 load_config 返回)
    mock: True 时不实际调用 Agent
    """
    pipelines = config.get("pipelines", {})
    pipeline = pipelines.get(pipeline_name)

    if not pipeline:
        print(f"[ERROR] 未知流水线: {pipeline_name}")
        print(f"       可用流水线: {list(pipelines.keys())}")
        return {"error": f"unknown pipeline: {pipeline_name}"}

    stages = pipeline.get("stages", [])
    if not stages:
        print(f"[ERROR] 流水线 {pipeline_name} 没有定义阶段")
        return {"error": "no stages defined"}

    # 共享工作目录
    work_dir_root = os.path.join(
        os.path.dirname(__file__),
        config.get("executor", {}).get("work_dir", "./sessions")
    )
    task_hash = hashlib.md5(
        f"{pipeline_name}:{original_task}".encode()
    ).hexdigest()[:8]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = os.path.join(work_dir_root, f"pipeline-{ts}-{task_hash}")
    os.makedirs(session_dir, exist_ok=True)

    timeout = config.get("executor", {}).get("timeout_seconds", 120)
    agents = config["agents"]
    match_weights = config["match_weights"]

    print("=" * 60)
    print(f"  AgentForge v0.2 -- Pipeline Mode")
    print(f"  Pipeline: {pipeline_name} -- {pipeline.get('description', '')}")
    print("=" * 60)
    print(f"\nTask: {original_task[:100]}")
    print(f"Dir:  {session_dir}\n")

    ctx: Dict[str, Any] = {
        "original_task": original_task,
        "stages": {},
        "previous_stage": None,
        "session_dir": session_dir,
    }

    for i, stage in enumerate(stages):
        stage_id = stage["id"]
        stage_type = stage["type"]
        stage_prompt_template = stage["prompt"]

        print(f"\n{'─' * 60}")
        print(f"  Stage {i + 1}/{len(stages)}: {stage_id} "
              f"-> {_TYPE_NAMES.get(stage_type, stage_type)}")
        print(f"{'─' * 60}\n")

        # 条件检查
        condition = stage.get("condition")
        if condition:
            cond_stage = condition.get("stage")
            cond_marker = condition.get("marker")
            cond_fallback = condition.get("fallback_check", False)

            if cond_stage in ctx["stages"]:
                prev_data = ctx["stages"][cond_stage]
                prev_out = prev_data.get("stdout", "")
                if not prev_data.get("success", False):
                    print(f"[SKIP] {stage_id} -- "
                          f"前置阶段 {cond_stage} 执行失败")
                    continue
                if cond_marker not in prev_out:
                    print(f"[SKIP] {stage_id} -- "
                          f"未检测到触发标志 '{cond_marker}'")
                    continue
            elif not cond_fallback:
                print(f"[SKIP] {stage_id} -- "
                      f"前置阶段 {cond_stage} 未执行")
                continue

        # 构建 prompt
        prompt = _build_prompt(stage_prompt_template, ctx, stage_id)

        prompt_preview = prompt[:200].replace("\n", "\n   ")
        print(f"Prompt (first 200 chars):\n   {prompt_preview}...\n")

        # 分类 — 流水线阶段使用声明类型，不走分类器
        task_type = stage_type
        type_label = _TYPE_NAMES.get(task_type, f"? {task_type}")
        print(f"Classify: {type_label} (from stage definition)")

        # 匹配
        match_result = match(task_type, agents, match_weights)
        if "error" in match_result:
            print(f"[ERROR] Match failed: {match_result['error']}")
            ctx["stages"][stage_id] = {
                "id": stage_id, "type": stage_type,
                "agent": "N/A", "stdout": "",
                "files": [], "success": False,
                "score": 0, "duration_ms": 0,
                "error": match_result["error"],
            }
            ctx["previous_stage"] = stage_id
            continue
        selected_agent = match_result["selected"]
        score = match_result["score"]
        description = match_result["description"]

        print(f"Match:    {selected_agent} "
              f"(score: {score:.2f}) -- {description}")

        for s in match_result["all_scores"]:
            bar = "#" * int(s["score"] * 20)
            marker = " <-" if s["name"] == selected_agent else ""
            print(f"   {s['name']:12s} {s['score']:.2f} {bar}{marker}")

        if mock:
            print("[MOCK] 跳过执行\n")
            ctx["stages"][stage_id] = {
                "id": stage_id,
                "type": stage_type,
                "agent": selected_agent,
                "stdout": (
                    f"[MOCK] 这是 {stage_id} 阶段的模拟输出。\n"
                    f"任务: {original_task}\n"
                    f"Agent: {selected_agent}"
                    f"{'__HAS_ISSUES__' if stage_id == 'review' else ''}"
                ),
                "files": [],
                "success": True,
                "score": score,
                "duration_ms": 0,
            }
            ctx["previous_stage"] = stage_id
            continue

        # 执行
        agent_config = agents[selected_agent]
        cli_command = agent_config["cli"]

        print(f"\nExec: {selected_agent} ({cli_command})")

        result = execute(
            agent_name=selected_agent,
            cli_command=cli_command,
            task=prompt,
            work_dir=work_dir_root,
            timeout=timeout,
            session_dir=session_dir,
            stage_prefix=stage_id,
        )

        # runner-up 降级：最佳 Agent 失败时自动换第二名
        if not result["success"] and match_result.get("runner_up"):
            runner = match_result["runner_up"]
            print(f"   [FALLBACK] {selected_agent} failed, trying {runner}...")
            runner_agent = agents[runner]
            result = execute(
                agent_name=runner,
                cli_command=runner_agent["cli"],
                task=prompt,
                work_dir=work_dir_root,
                timeout=timeout,
                session_dir=session_dir,
                stage_prefix=stage_id,
            )
            if result["success"]:
                selected_agent = runner

        ctx["stages"][stage_id] = {
            "id": stage_id,
            "type": stage_type,
            "agent": selected_agent,
            "stdout": result.get("stdout", ""),
            "files": result.get("produced_files", []),
            "success": result.get("success", False),
            "score": score,
            "duration_ms": result.get("duration_ms", 0),
        }
        ctx["previous_stage"] = stage_id

        if result["success"]:
            print(f"[OK] {stage_id} -- {result['duration_ms']}ms")
            if result.get("stdout"):
                out_preview = result["stdout"][:200].replace("\n", "\n   ")
                print(f"   output: {out_preview}")
        else:
            err = result.get("error") or f"exit {result.get('exit_code')}"
            print(f"[WARN] {stage_id} 失败 -- {err}")
            print(f"       流水线继续执行后续阶段")

    # 最终汇总
    _print_summary(ctx)
    _save_summary(ctx, session_dir, pipeline_name)

    return ctx["stages"]


def _build_prompt(template: str, ctx: dict, stage_id: str) -> str:
    """将模板中的占位符替换为上下文实际值"""
    previous_stage = ctx.get("previous_stage")
    prev_data = ctx["stages"].get(previous_stage) if previous_stage else None

    prompt = template.replace("{original_task}", ctx["original_task"])
    prompt = prompt.replace("{stage_id}", stage_id)

    if prev_data:
        prompt = prompt.replace(
            "{previous_agent}", prev_data.get("agent", "unknown")
        )
        prompt = prompt.replace(
            "{previous_stdout}", prev_data.get("stdout", "")
        )
        prompt = prompt.replace(
            "{previous_files}",
            _format_file_list(prev_data.get("files", []))
        )
    else:
        prompt = prompt.replace("{previous_agent}", "(none)")
        prompt = prompt.replace("{previous_stdout}", "")
        prompt = prompt.replace("{previous_files}", "(none)")

    # 所有阶段的文件汇总
    all_files: list = []
    for sdata in ctx.get("stages", {}).values():
        all_files.extend(sdata.get("files", []))
    prompt = prompt.replace("{all_files}", _format_file_list(all_files))

    # 所有阶段的上下文摘要
    prompt = prompt.replace(
        "{stages_summary}",
        _format_stages_summary(ctx["stages"])
    )

    return prompt


def _format_file_list(files: list) -> str:
    """格式化文件列表为字符串"""
    if not files:
        return "(none)"
    lines = []
    for f in files:
        lines.append(f"  - {f['path']} ({f['size']} bytes)")
    return "\n".join(lines)


def _format_stages_summary(stages: dict) -> str:
    """格式化所有已完成阶段的摘要"""
    if not stages:
        return "(none)"
    lines = []
    for sid, sdata in stages.items():
        status = "[OK]" if sdata.get("success") else "[FAIL]"
        lines.append(
            f"{status} {sid}: {sdata.get('agent', '?')} "
            f"({sdata.get('duration_ms', 0)}ms)"
        )
        stdout = sdata.get("stdout", "")
        if stdout:
            lines.append(f"   output: {stdout[:300]}")
    return "\n".join(lines)


def _print_summary(ctx: dict):
    """打印流水线完成汇总"""
    stages = ctx.get("stages", {})
    print(f"\n{'=' * 60}")
    print(f"  Pipeline Summary")
    print(f"{'=' * 60}\n")

    for sid, sdata in stages.items():
        status = "[OK]" if sdata["success"] else "[FAIL]"
        files_count = len(sdata.get("files", []))
        print(f"  {status} {sid}: {sdata['agent']} "
              f"({sdata.get('duration_ms', 0)}ms) -- {files_count} files")


def _save_summary(ctx: dict, session_dir: str, pipeline_name: str):
    """保存流水线结果摘要到 JSON"""
    summary = {
        "pipeline": pipeline_name,
        "original_task": ctx["original_task"],
        "session_dir": ctx["session_dir"],
        "stages": {
            sid: {
                "id": sdata.get("id", sid),
                "type": sdata.get("type", ""),
                "agent": sdata.get("agent", ""),
                "success": sdata.get("success", False),
                "score": sdata.get("score", 0),
                "duration_ms": sdata.get("duration_ms", 0),
                "files_count": len(sdata.get("files", [])),
                "stdout_preview": (sdata.get("stdout", "") or "")[:500],
            }
            for sid, sdata in ctx.get("stages", {}).items()
        },
        "timestamp": datetime.now().isoformat(),
    }
    summary_path = os.path.join(session_dir, "pipeline_result.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nArchive: {session_dir}")
    print(f"Summary: pipeline_result.json")
