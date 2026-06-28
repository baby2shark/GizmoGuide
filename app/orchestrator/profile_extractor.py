from __future__ import annotations

import re

from app.schemas.user_profile import Scenario, UserProfile
from app.tracing import trace_span

SCENARIO_KEYWORDS: list[tuple[Scenario, tuple[str, ...]]] = [
    (Scenario.photo, ("拍照", "摄影", "影像", "相机", "人像", "视频", "vlog")),
    (Scenario.gaming, ("游戏", "原神", "王者", "吃鸡", "性能", "散热")),
    (Scenario.elder, ("老人", "父母", "长辈", "字体", "简单")),
    (Scenario.student, ("学生", "上学", "宿舍", "性价比", "便宜")),
    (Scenario.business, ("商务", "办公", "出差", "会议", "邮件")),
    (Scenario.travel, ("旅行", "旅游", "出门", "续航", "导航")),
    (Scenario.daily, ("日常", "刷视频", "微信", "轻度", "普通使用")),
]


def extract_profile(message: str, existing: UserProfile | None = None) -> UserProfile:
    with trace_span("profile_extraction", input_data={"message": message[:200]}) as (span, end_span):
        profile = existing.model_copy(deep=True) if existing else UserProfile()
        text = message.lower()

        budget = _extract_budget(text)
        if budget is not None:
            profile.budget = budget

        years = _extract_usage_years(text)
        if years is not None:
            profile.usage_years = years

        scenarios = set(profile.primary_scenarios)
        for scenario, keywords in SCENARIO_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                scenarios.add(scenario)
        profile.primary_scenarios = list(scenarios)

        if any(word in text for word in ("苹果", "iphone", "ios")):
            profile.os_preference = "ios"
        elif any(word in text for word in ("安卓", "android", "鸿蒙")):
            profile.os_preference = "android"

        if any(word in text for word in ("维修", "售后", "修", "耐用", "用久")):
            profile.repair_sensitivity = "high"
        if any(word in text for word in ("风险低", "稳", "稳定", "别翻车")):
            profile.risk_tolerance = "low"
        if any(word in text for word in ("便宜", "预算紧", "省钱", "性价比")):
            profile.budget_flexibility = "low"

        storage = _extract_storage(text)
        if storage is not None:
            profile.min_storage_gb = storage

        weight = _extract_weight_limit(text)
        if weight is not None:
            profile.max_weight_g = weight

        end_span(output=profile.model_dump(mode="json"))
        return profile


def build_clarification_questions(profile: UserProfile) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    if profile.budget is None:
        questions.append({"field": "budget", "question": "预算大概是多少？可以给一个上限。"})
    if not profile.primary_scenarios:
        questions.append({"field": "primary_scenarios", "question": "主要用来做什么？比如拍照、游戏、日常、办公或给长辈用。"})
    if profile.usage_years is None:
        questions.append({"field": "usage_years", "question": "你希望这台手机大概用几年？"})
    return questions[:3]


def _extract_budget(text: str) -> int | None:
    patterns = [
        r"预算\s*(\d{3,5})",
        r"(\d{3,5})\s*(?:元|块|以内|以下|左右)",
        r"(\d(?:\.\d+)?)\s*[w万]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = float(match.group(1))
        if "万" in match.group(0) or "w" in match.group(0):
            value *= 10000
        return int(value)
    return None


def _extract_usage_years(text: str) -> int | None:
    zh_digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
    match = re.search(r"用\s*(\d)\s*年", text)
    if match:
        return int(match.group(1))
    match = re.search(r"用\s*([一二两三四五六七八])\s*年", text)
    if match:
        return zh_digits[match.group(1)]
    match = re.search(r"(\d)\s*年", text)
    if match and any(word in text for word in ("用", "换机", "耐用")):
        return int(match.group(1))
    match = re.search(r"([一二两三四五六七八])\s*年", text)
    if match and any(word in text for word in ("用", "换机", "耐用")):
        return zh_digits[match.group(1)]
    return None


def _extract_storage(text: str) -> int | None:
    match = re.search(r"(128|256|512|1024)\s*g", text)
    return int(match.group(1)) if match else None


def _extract_weight_limit(text: str) -> int | None:
    match = re.search(r"(\d{3})\s*g", text)
    if match and any(word in text for word in ("轻", "重量", "别太重", "以内")):
        return int(match.group(1))
    return None

