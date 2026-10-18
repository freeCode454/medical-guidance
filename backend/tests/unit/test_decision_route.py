"""分诊决策表：路由阈值是安全与体验的平衡点，单独锁行为。"""
from __future__ import annotations

from app.agents.nodes.triage_router import _decide_route


def test_no_candidates_goes_manual() -> None:
    assert _decide_route(0.99, []) == "MANUAL"


def test_close_candidates_go_mdt() -> None:
    depts = [{"confidence": 0.9}, {"confidence": 0.85}]
    assert _decide_route(0.9, depts) == "MDT"


def test_clear_winner_goes_direct() -> None:
    depts = [{"confidence": 0.9}, {"confidence": 0.5}]
    assert _decide_route(0.9, depts) == "DIRECT"


def test_low_confidence_goes_manual() -> None:
    assert _decide_route(0.2, [{"confidence": 0.2}]) == "MANUAL"
