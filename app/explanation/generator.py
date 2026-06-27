from __future__ import annotations

from app.schemas.recommendation import RecommendationResult
from app.schemas.user_profile import UserProfile


def generate_answer(result: RecommendationResult, profile: UserProfile) -> str:
    scenario_text = "、".join(item.value for item in profile.primary_scenarios) or "未明确"
    budget_text = f"预算 {profile.budget} 元" if profile.budget else "预算未明确"

    lines = [
        f"更推荐 {result.winner_name}。",
        f"当前判断基于：{budget_text}，主要场景：{scenario_text}，置信度 {result.confidence:.0%}。",
        "",
        "主要理由：",
    ]
    lines.extend(f"- {reason}" for reason in result.key_reasons)
    lines.append("")
    lines.append("风险提示：")
    lines.extend(f"- {risk}" for risk in result.risks)
    lines.append("")
    lines.append("结论可能反转的情况：")
    lines.extend(f"- {condition}" for condition in result.reversal_conditions)
    if result.missing_information:
        lines.append("")
        lines.append("目前缺失的信息：")
        lines.extend(f"- {item}" for item in result.missing_information)
    return "\n".join(lines)
