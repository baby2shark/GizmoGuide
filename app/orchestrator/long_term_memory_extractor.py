from __future__ import annotations

import re

from app.schemas.long_term_memory import UserPreferenceMemory
from app.schemas.user_profile import Scenario, UserProfile

BRANDS = (
    "苹果",
    "iphone",
    "三星",
    "华为",
    "小米",
    "redmi",
    "oppo",
    "vivo",
    "荣耀",
    "一加",
    "iqoo",
    "真我",
    "realme",
)

PREFERRED_FEATURE_RULES: dict[str, tuple[str, ...]] = {
    "小屏": ("小屏", "单手", "别太大"),
    "轻薄": ("轻薄", "轻一点", "别太重"),
    "长续航": ("续航", "耐用", "电池大"),
    "快充": ("快充", "充电快"),
    "拍照": ("拍照", "摄影", "人像", "影像"),
    "游戏": ("游戏", "性能", "散热"),
    "长焦": ("长焦", "拍远", "演唱会"),
    "无线充": ("无线充",),
    "直屏": ("直屏",),
    "折叠屏": ("折叠屏", "大折叠", "小折叠"),
}

DISLIKED_FEATURE_RULES: dict[str, tuple[str, ...]] = {
    "曲面屏": ("不要曲面", "别要曲面", "曲面屏不要"),
    "太重": ("别太重", "太重不要"),
    "发热": ("别发热", "不要太热", "发热小一点"),
    "折叠屏": ("不考虑折叠", "不要折叠屏"),
}


def merge_profiles(base: UserProfile | None, override: UserProfile | None) -> UserProfile:
    """Merge two profile snapshots, preferring explicit values from override."""
    if base is None and override is None:
        return UserProfile()
    if base is None:
        return override.model_copy(deep=True) if override else UserProfile()
    if override is None:
        return base.model_copy(deep=True)

    merged = base.model_copy(deep=True)
    for field_name in (
        "budget",
        "budget_flexibility",
        "usage_years",
        "brand_preference",
        "os_preference",
        "risk_tolerance",
        "repair_sensitivity",
        "min_storage_gb",
        "max_weight_g",
    ):
        value = getattr(override, field_name)
        if value is not None:
            setattr(merged, field_name, value)

    merged.primary_scenarios = _dedupe_strings(
        [scenario.value for scenario in base.primary_scenarios]
        + [scenario.value for scenario in override.primary_scenarios]
    )
    merged.primary_scenarios = [Scenario(item) for item in merged.primary_scenarios]
    merged.notes = _dedupe_strings(base.notes + override.notes)
    return merged


def extract_preference_memory(message: str, existing: UserPreferenceMemory | None = None) -> UserPreferenceMemory:
    """Extract stable preference memory from a user message."""
    memory = existing.model_copy(deep=True) if existing else UserPreferenceMemory()
    text = message.lower()

    if any(word in text for word in ("苹果", "iphone", "ios")):
        memory.os_preference = "ios"
    elif any(word in text for word in ("安卓", "android", "鸿蒙")):
        memory.os_preference = "android"

    memory.preferred_brands = _dedupe_strings(memory.preferred_brands + _extract_preferred_brands(text))
    memory.avoided_brands = _dedupe_strings(memory.avoided_brands + _extract_avoided_brands(text))

    if any(word in text for word in ("预算紧", "省钱", "便宜点", "性价比")):
        memory.budget_flexibility = "low"
    elif any(word in text for word in ("预算可以加", "贵一点也行", "价格不是问题")):
        memory.budget_flexibility = "high"

    if any(word in text for word in ("别翻车", "稳定", "风险低", "省心")):
        memory.risk_tolerance = "low"
    elif any(word in text for word in ("尝鲜", "新鲜功能", "可以接受风险")):
        memory.risk_tolerance = "high"

    if any(word in text for word in ("维修", "售后", "耐用", "修起来麻烦")):
        memory.repair_sensitivity = "high"

    for feature, keywords in PREFERRED_FEATURE_RULES.items():
        if any(keyword in text for keyword in keywords):
            memory.preferred_features.append(feature)

    for feature, keywords in DISLIKED_FEATURE_RULES.items():
        if any(keyword in text for keyword in keywords):
            memory.disliked_features.append(feature)

    note = _extract_preference_note(message)
    if note:
        memory.notes = _dedupe_strings(memory.notes + [note])

    memory.preferred_features = _dedupe_strings(memory.preferred_features)
    memory.disliked_features = _dedupe_strings(memory.disliked_features)
    return memory


def _extract_preferred_brands(text: str) -> list[str]:
    matches: list[str] = []
    for brand in BRANDS:
        if brand not in text:
            continue
        if re.search(rf"(喜欢|想买|倾向|偏向|优先|只看).{{0,4}}{re.escape(brand)}", text) or re.search(
            rf"{re.escape(brand)}.{{0,4}}(可以|优先|也行|最好)",
            text,
        ):
            matches.append(_normalize_brand(brand))
    return matches


def _extract_avoided_brands(text: str) -> list[str]:
    matches: list[str] = []
    for brand in BRANDS:
        if brand not in text:
            continue
        if re.search(rf"(不要|不想要|不考虑|排除).{{0,4}}{re.escape(brand)}", text):
            matches.append(_normalize_brand(brand))
    return matches


def _extract_preference_note(message: str) -> str | None:
    stripped = message.strip()
    if len(stripped) < 8 or len(stripped) > 80:
        return None
    if any(word in stripped for word in ("喜欢", "不喜欢", "最好", "不要", "希望", "更在意", "主要")):
        return stripped
    return None


def _normalize_brand(brand: str) -> str:
    mapping = {
        "iphone": "苹果",
        "redmi": "Redmi",
        "iqoo": "iQOO",
        "realme": "realme",
    }
    return mapping.get(brand, brand.capitalize() if brand.isascii() else brand)


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
