"""应用配置。

铁律：**所有环境差异由配置值驱动**。业务代码中不得出现
`if settings.deploy_mode == "dev"` 这类分支，否则代码会分叉成两套。

开发期与交付期的差异集中在少数几个值：
`llm_base_url` / `embedding_base_url` / `rerank_base_url` / `milvus_uri` / `database_url`

**出域策略（`egress_policy`）是独立于部署形态的开关**，不随环境名称自动放宽。
交付形态（`deploy_mode=prod`）只允许 `strict`；若误配为 `dev_sandbox`，
启动校验会直接拒绝启动——宁可起不来，也不要带着数据外泄风险运行。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.common.egress_guard import EgressPolicy, is_private_host

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------- 运行环境 ----------------
    # deploy_mode 描述「部署形态」，egress_policy 描述「出域策略」。
    # 两者正交：策略不随环境名称自动放宽（NFR70）。
    deploy_mode: Literal["dev", "prod"] = "dev"
    egress_policy: EgressPolicy = EgressPolicy.STRICT
    debug_endpoints: bool = False

    # ---------------- HTTP / 可观测性 ----------------
    # 逗号分隔的允许来源；生产由网关同源托管时可留空
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    log_level: str = "INFO"

    # ---------------- 内容生成（OpenAI 兼容） ----------------
    llm_base_url: str
    llm_api_key: str = ""
    llm_model: str = "Qwen/Qwen2.5-32B-Instruct"
    small_llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_timeout_seconds: float = 60.0

    # ---------------- 向量化 ----------------
    # provider=local：本地 BGE-M3，同时产出稠密 + 稀疏向量（主力）
    # provider=api  ：云端 BGE-M3，只产出稠密向量（用于校验本地量化）
    embedding_provider: Literal["api", "local"] = "api"
    embedding_model_path: str = ""
    embedding_batch_size: int = 8
    embedding_max_length: int = 512
    embedding_use_fp16: bool = False  # CPU 上开启会更慢
    embedding_sparse_top_k: int = 256

    # provider=api 时使用；留空表示与 llm_base_url 同网关
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"

    # ---------------- 精排 ----------------
    # 与向量化解耦：向量化可本地，精排可云端，二者互不影响
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_base_url: str = ""  # 留空表示与 llm_base_url 同网关
    rerank_api_key: str = ""
    rerank_enabled: bool = True
    # 开发期 CPU 不适合大量候选，先收敛；生产环境可放开到 20~30
    rerank_candidates: int = 8

    # ---------------- 存储 ----------------
    # 向量库：开发/交付统一用 Milvus Standalone（Milvus Lite 不支持 Windows）
    milvus_uri: str = "http://localhost:19530"
    database_url: str = "postgresql+asyncpg://medguide:medguide@localhost:5434/medguide"
    redis_url: str = "redis://localhost:6379/0"

    # 对象存储（MinIO，S3 兼容）
    object_storage_endpoint: str = "localhost:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "medguide"
    object_storage_secure: bool = False

    # ---------------- 认证与安全 ----------------
    # 开发期可沿用默认值；交付形态（prod）会强制校验非默认（见 _validate）
    # 默认值长度须 >= 32 字节（HMAC-SHA256 推荐下限），否则 pyjwt 会告警
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    # 三档有效期（秒）：院内用户访问令牌 / 刷新令牌 / 匿名患者令牌
    access_token_expires_seconds: int = 7200
    refresh_token_expires_seconds: int = 28800
    patient_token_expires_seconds: int = 1800
    # 匿名患者绑定的默认租户（种子数据 HOSP_001）。多租户入口识别为后续扩展
    default_tenant_id: str = "00000000000000000000000000000001"

    # ---------------- 能力开关 ----------------
    asr_enabled: bool = False
    tracing_enabled: bool = False

    # ---------------- 派生属性 ----------------

    @property
    def effective_embedding_base_url(self) -> str:
        """仅 embedding_provider=api 时使用。"""
        return self.embedding_base_url or self.llm_base_url

    @property
    def effective_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.llm_api_key or "not-needed"

    @property
    def effective_rerank_base_url(self) -> str:
        return self.rerank_base_url or self.llm_base_url

    @property
    def effective_rerank_api_key(self) -> str:
        return self.rerank_api_key or self.llm_api_key or "not-needed"

    @property
    def embedding_is_local(self) -> bool:
        return self.embedding_provider == "local"

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的 CORS_ORIGINS 解析成列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # ---------------- 启动校验 ----------------

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        """院内网模式下，关键服务地址必须为内网地址。

        校验不通过则启动失败——宁可起不来，也不要带着数据外泄风险运行。
        """
        # ---- 本地向量模型的路径必须真实存在，否则启动即失败 ----
        if self.embedding_is_local:
            if not self.embedding_model_path:
                raise ValueError(
                    "embedding_provider=local 时必须配置 EMBEDDING_MODEL_PATH"
                )
            model_dir = Path(self.embedding_model_path)
            if not model_dir.is_dir():
                raise ValueError(f"本地向量模型目录不存在：{model_dir}")
            required = ("config.json", "tokenizer.json")
            missing = [name for name in required if not (model_dir / name).exists()]
            if missing:
                raise ValueError(f"本地向量模型目录缺少必要文件 {missing}：{model_dir}")

            # 权重文件：ONNX 与 PyTorch 二者任一即可。
            # 本项目采用 ONNX Runtime 推理（不引入 torch，镜像体积少约 2 GB），
            # 因此优先检查 onnx/ 子目录。
            onnx_model = model_dir / "onnx" / "model.onnx"
            has_torch = (model_dir / "pytorch_model.bin").exists()
            if not onnx_model.exists() and not has_torch:
                raise ValueError(
                    "本地向量模型目录缺少权重文件"
                    f"（onnx/model.onnx 或 pytorch_model.bin）：{model_dir}"
                )
            if not onnx_model.exists():
                logger.warning(
                    "未找到 onnx/model.onnx（%s），将回退到 PyTorch 权重。"
                    "注意：PyTorch 路线需额外安装 torch，镜像体积约增加 2 GB。",
                    model_dir,
                )

            if not (model_dir / "sparse_linear.pt").exists():
                logger.warning(
                    "本地向量模型缺少 sparse_linear.pt（稀疏检索权重，%s），"
                    "将无法产出稀疏向量，混合检索会退化为纯稠密检索",
                    model_dir,
                )

        # ---- 交付形态不得使用开发形态的出域策略 ----
        if self.deploy_mode == "prod" and self.egress_policy is EgressPolicy.DEV_SANDBOX:
            raise ValueError(
                "deploy_mode=prod 时不允许 egress_policy=dev_sandbox。\n"
                "dev_sandbox 会放行患者链路能力（内容生成、精排、知识库检索）的院外调用，"
                "仅适用于无本地推理算力的开发环境。"
            )

        # ---- 交付形态不得使用默认凭证 ----
        if self.deploy_mode == "prod":
            if self.jwt_secret == "dev-only-secret-change-me-0123456789abcdef":
                raise ValueError("deploy_mode=prod 时必须配置 JWT_SECRET，不得使用开发默认值")
            for name, default, value in (
                ("OBJECT_STORAGE_ACCESS_KEY", "minioadmin", self.object_storage_access_key),
                ("OBJECT_STORAGE_SECRET_KEY", "minioadmin", self.object_storage_secret_key),
            ):
                if value == default:
                    raise ValueError(f"deploy_mode=prod 时 {name} 不得使用默认值")

        # ---- strict 策略下不得指向院外地址 ----
        if self.egress_policy is EgressPolicy.STRICT:
            targets = {"LLM_BASE_URL": self.llm_base_url}
            if not self.embedding_is_local:
                targets["EMBEDDING_BASE_URL"] = self.effective_embedding_base_url
            if self.rerank_enabled:
                targets["RERANK_BASE_URL"] = self.effective_rerank_base_url
            for name, url in targets.items():
                if not is_private_host(url):
                    raise ValueError(
                        f"egress_policy=strict 时 {name} 必须为内网地址，当前为 {url!r}。\n"
                        "开发形态请显式设置 EGRESS_POLICY=dev_sandbox。"
                    )
        else:
            # 开发形态允许院外地址，但要求显式声明，并在缺凭证时提前告警
            logger.warning(
                "出域策略为 dev_sandbox：内容生成与精排的院外调用将被放行。"
                "该形态仅允许使用合成数据，交付前必须改回 strict。"
            )
            if not is_private_host(self.llm_base_url) and not self.llm_api_key:
                logger.warning(
                    "指向院外内容生成服务（%s）但未配置 LLM_API_KEY，调用将失败",
                    self.llm_base_url,
                )
            if (
                self.rerank_enabled
                and not is_private_host(self.effective_rerank_base_url)
                and not self.effective_rerank_api_key.strip()
            ):
                logger.warning("精排指向院外服务但未配置 RERANK_API_KEY，调用将失败")
        return self


def load_settings() -> Settings:
    """显式加载配置。避免模块导入期就因为缺环境变量而崩溃，便于测试。"""
    return Settings()


settings = load_settings()
