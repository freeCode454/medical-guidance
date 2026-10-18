"""出域守卫：数据安全是硬约束，必须用测试锁死。"""
from __future__ import annotations

import pytest

from app.common.egress_guard import (
    DataResidencyViolation,
    EgressGuard,
    EgressPolicy,
    is_private_host,
)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("10.1.2.3", True),
        ("192.168.1.10", True),
        ("127.0.0.1", True),
        ("localhost", True),
        ("llm.intranet", True),
        ("vllm-svc.local", True),
        ("api.siliconflow.cn", False),
        ("8.8.8.8", False),
        ("example.com", False),
    ],
)
def test_private_host_detection(host: str, expected: bool) -> None:
    assert is_private_host(host) is expected


def test_intranet_target_is_always_allowed() -> None:
    guard = EgressGuard(EgressPolicy.STRICT)
    guard.check("patient_profile", "http://his.intranet:8080")


def test_strict_denies_external_even_for_llm() -> None:
    guard = EgressGuard(EgressPolicy.STRICT)
    with pytest.raises(DataResidencyViolation):
        guard.check("llm_chat", "https://api.siliconflow.cn/v1")


def test_patient_pii_never_leaves_even_in_sandbox() -> None:
    guard = EgressGuard(EgressPolicy.DEV_SANDBOX)
    with pytest.raises(DataResidencyViolation):
        guard.check("emr_query", "https://api.example.com/v1", is_synthetic=True)


def test_sandbox_requires_synthetic_and_audits() -> None:
    recorded: list[tuple[str, str]] = []
    guard = EgressGuard(EgressPolicy.DEV_SANDBOX, on_egress=lambda c, h: recorded.append((c, h)))

    with pytest.raises(DataResidencyViolation):
        guard.check("llm_chat", "https://api.siliconflow.cn/v1", is_synthetic=False)

    guard.check("llm_chat", "https://api.siliconflow.cn/v1", is_synthetic=True)
    assert recorded == [("llm_chat", "api.siliconflow.cn")]


def test_non_patient_capability_allowed_in_sandbox() -> None:
    guard = EgressGuard(EgressPolicy.DEV_SANDBOX)
    guard.check("kb_build", "https://api.siliconflow.cn/v1", is_synthetic=False)
