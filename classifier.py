"""
AgentForge — 任务分类器
根据关键词匹配确定任务类型、提取技术栈信息
"""
import re
from typing import Tuple


def classify(task: str, rules: list, fallback: str = "coding") -> Tuple[str, dict]:
    """
    输入: 自然语言任务描述
    输出: (任务类型, 元信息)
    
    元信息包含:
      - matched_keywords: 命中的关键词
      - matched_targets: 命中的对象
      - has_code_context: 是否提到具体文件/代码
    """
    task_lower = task.lower()

    for rule in rules:
        rule_type = rule["type"]
        keywords = rule.get("keywords", [])
        targets = rule.get("targets", [])

        # 检查关键词命中
        matched_kw = [kw for kw in keywords if kw.lower() in task_lower]
        if not matched_kw:
            continue

        # 检查对象命中
        matched_tg = []
        if targets:
            matched_tg = [t for t in targets if t.lower() in task_lower]
            if not matched_tg:
                continue  # 有 targets 但没命中 → 不是这个类型

        return rule_type, {
            "matched_keywords": matched_kw,
            "matched_targets": matched_tg,
            "has_code_context": bool(
                re.search(r"这段代码|这个文件|\.ts|\.py|\.js|\.vue", task_lower)
            ),
        }

    return fallback, {
        "matched_keywords": [],
        "matched_targets": [],
        "has_code_context": False,
        "reason": "no_rule_matched",
    }
