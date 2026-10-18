"""规则引擎：同义词归一化、红旗命中、分诊规则加权。"""
from __future__ import annotations

import pytest

from app.agents.nodes.safety import detect_emergency
from app.services import rules_engine


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("肚子疼三天了", "腹痛"),
        ("拉肚子", "腹泻"),
        ("胸口疼冒冷汗", "胸痛"),
    ],
)
def test_normalize_complaint(text: str, expected: str) -> None:
    assert expected in rules_engine.normalize_complaint(text)


@pytest.mark.parametrize(
    "text",
    ["胸口疼冒冷汗", "突然昏迷", "呕血", "喘不上气"],
)
def test_emergency_detection_covers_rule_and_fallback(text: str) -> None:
    """危重症识别 = 规则库 + 硬编码兜底；两者任一命中都必须拦住。"""
    assert detect_emergency(text), f"应判定为危重症：{text}"


def test_rule_library_hits_colloquial_chest_pain() -> None:
    assert rules_engine.match_red_flags("胸口疼冒冷汗")


def test_red_flags_miss_common_complaint() -> None:
    assert rules_engine.match_red_flags("肚子疼三天了，有点拉肚子") == []


def test_dept_bonus_prefers_digestive() -> None:
    bonus = rules_engine.match_dept_bonus("肚子疼三天了，还拉肚子")
    assert bonus.get("DIG", 0) > 0


def test_inquiry_template_type_inference() -> None:
    assert rules_engine.infer_complaint_type("肚子疼三天了") == "腹痛"
    templates = rules_engine.inquiry_templates("腹痛")
    assert templates
    assert templates == sorted(templates, key=lambda item: int(item.get("order") or 99))
