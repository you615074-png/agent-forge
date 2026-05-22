"""
AgentForge — 能力匹配引擎
根据任务类型和 Agent 能力卡，计算最佳匹配
"""
from typing import Dict


def match(task_type: str, agents: dict, weights: dict) -> dict:
    """
    输入: 任务类型, Agent 能力卡, 权重配置
    输出: { agent_name, score, details }
    
    算法: Σ(Agent能力 × 权重) / Σ权重
    """
    type_weights = weights.get(task_type, {})
    if not type_weights:
        return {"error": f"unknown task type: {task_type}"}

    results = []

    for name, agent in agents.items():
        caps = agent.get("capabilities", {})
        score = 0.0
        total_weight = 0.0
        breakdown = {}

        for dim, weight in type_weights.items():
            cap_score = caps.get(dim, 0)
            score += cap_score * weight
            total_weight += weight
            breakdown[dim] = {
                "agent_score": cap_score,
                "weight": weight,
                "contribution": round(cap_score * weight, 3),
            }

        normalized = round(score / total_weight, 4) if total_weight > 0 else 0

        results.append({
            "name": name,
            "score": normalized,
            "breakdown": breakdown,
            "description": agent.get("description", ""),
        })

    # 按得分降序
    results.sort(key=lambda x: x["score"], reverse=True)

    best = results[0]
    runner_up = results[1] if len(results) > 1 else None

    return {
        "selected": best["name"],
        "score": best["score"],
        "description": best["description"],
        "runner_up": runner_up["name"] if runner_up else None,
        "runner_up_score": runner_up["score"] if runner_up else None,
        "all_scores": [
            {"name": r["name"], "score": r["score"]} for r in results
        ],
    }
