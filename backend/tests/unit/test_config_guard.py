"""启动配置校验：宁可起不来，也不要带着数据外泄风险运行。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.common.egress_guard import EgressPolicy
from app.config import Settings


def test_strict_policy_rejects_public_llm_endpoint() -> None:
    with pytest.raises(ValidationError, match="必须为内网地址"):
        Settings(
            _env_file=None,
            llm_base_url="https://api.siliconflow.cn/v1",
            egress_policy=EgressPolicy.STRICT,
        )


def test_prod_rejects_dev_sandbox() -> None:
    with pytest.raises(ValidationError, match="不允许 egress_policy=dev_sandbox"):
        Settings(
            _env_file=None,
            deploy_mode="prod",
            egress_policy=EgressPolicy.DEV_SANDBOX,
            llm_base_url="http://10.0.0.5:8000/v1",
        )


def test_prod_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            deploy_mode="prod",
            egress_policy=EgressPolicy.STRICT,
            llm_base_url="http://10.0.0.5:8000/v1",
        )


def test_prod_rejects_memory_checkpoint() -> None:
    with pytest.raises(ValidationError, match="checkpoint_backend"):
        Settings(
            _env_file=None,
            deploy_mode="prod",
            egress_policy=EgressPolicy.STRICT,
            llm_base_url="http://10.0.0.5:8000/v1",
            jwt_secret="x" * 40,
            object_storage_access_key="real-key",
            object_storage_secret_key="real-secret",
            checkpoint_backend="memory",
        )


def test_checkpoint_pool_bounds() -> None:
    with pytest.raises(ValidationError, match="连接池"):
        Settings(
            _env_file=None,
            checkpoint_pool_min_size=5,
            checkpoint_pool_max_size=2,
        )


def test_dev_sandbox_allows_public_endpoint() -> None:
    settings = Settings(
        _env_file=None,
        deploy_mode="dev",
        egress_policy=EgressPolicy.DEV_SANDBOX,
        llm_base_url="https://api.siliconflow.cn/v1",
    )
    assert settings.egress_policy is EgressPolicy.DEV_SANDBOX
    assert settings.cors_origin_list[0].startswith("http://localhost")
