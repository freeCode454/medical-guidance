"""数据出域守卫。

对应文档：02 文档 §8.2、`NFR56`、`NFR70`、`ADR-008`。

**核心设计：按「能力 + 目标地址」双维度判定，而不是一个全局开关。**
全局开关一旦打开，患者数据也会被一并放出去；而按能力判定可以做到
「内容生成可以出域，病历查询永远不行」。

两级判定，顺序不可颠倒：

1. **绝对禁止出域的能力**（病历查询、患者信息、真实语音、病历文书检索）
   —— 任何策略、任何地址，只要目标在院外一律拒绝，**不存在例外**。
2. **患者链路但开发形态可放行的能力**（内容生成、精排、知识库检索）
   —— `strict` 下院外一律拒绝；`dev_sandbox` 下可放行，但必须同时满足
   四项约束（见 `EgressGuard.check` 的 docstring）。

`dev_sandbox` **不是「宽松版守卫」**，而是「带附加约束的开发形态」。
它存在的唯一理由是：开发机没有本地推理算力，主流程必须调用院外模型
才能跑通；与其悄悄放宽，不如把放宽的条件显式写进代码。
"""

from __future__ import annotations

import ipaddress
import logging
from enum import Enum
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class EgressPolicy(str, Enum):
    """出域策略。

    注意取值是**策略名**而非环境名——避免出现「看环境自动放宽」的隐式分支
    （`NFR70` 明确禁止）。环境与策略是正交的两个维度：

    | 环境 | 允许的策略 |
    |---|---|
    | 开发 | `strict` 或 `dev_sandbox` |
    | 交付 | 仅 `strict` |
    """

    STRICT = "strict"  # 患者数据能力的目标地址在院外一律拒绝
    DEV_SANDBOX = "dev_sandbox"  # 仅开发形态；放行需满足四项约束


class DataResidencyViolation(RuntimeError):
    """违反数据驻留策略。

    调用方**不得**捕获后继续执行——按数据安全要求，这类调用必须直接失败。
    """


# ---- 能力分类 ----------------------------------------------------------------

# 绝对禁止出域：涉及患者原始数据，任何策略下都不得访问院外地址
ABSOLUTE_PII_CAPABILITIES: frozenset[str] = frozenset(
    {
        "emr_query",  # 既往病历查询
        "patient_profile",  # 患者信息读取
        "asr_realtime",  # 真实患者语音转写
        "kb_emr_retrieval",  # 病历文书检索
    }
)

# 患者链路能力：开发形态下可放行，交付形态下院外一律拒绝
PATIENT_PIPELINE_CAPABILITIES: frozenset[str] = frozenset(
    {
        "llm_chat",  # 内容生成（澄清追问、MDT 会诊、病历生成）
        "llm_embed",  # 在线向量化（患者文本可能进入）
        "rerank",  # 结果精排
        "kb_retrieval",  # 知识库检索
    }
)

# 不含患者数据的能力：出域限制只受部署形态约束
NON_PII_CAPABILITIES: frozenset[str] = frozenset(
    {
        "kb_build",  # 知识库离线构建
        "embedding_offline",  # 离线向量化
        "tracing",  # 链路追踪
    }
)

# 兼容旧调用方：任何环境都不得出域的能力集合
PII_CAPABILITIES = ABSOLUTE_PII_CAPABILITIES

# 合成病例的患者标识前缀。开发形态下的数据必须带头该前缀，
# 便于审计时一眼区分合成数据与真实数据。
SYNTHETIC_PATIENT_PREFIX = "DEV_"

# 明确视为内网的域名后缀
_PRIVATE_SUFFIXES = (".local", ".intranet", ".internal", ".lan")

_LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def is_private_host(host_or_url: str) -> bool:
    """判断目标是否属于院内网络。

    无法判定时一律返回 False（按不安全处理）——宁可误拦，不可误放。
    """
    host = urlparse(host_or_url).hostname if "://" in host_or_url else host_or_url
    if not host:
        return False

    host = host.lower().strip("[]")
    if host in _LOOPBACK_NAMES or host.endswith(_PRIVATE_SUFFIXES):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # 非 IP 且非已知内网域名 → 按院外处理
    return ip.is_private or ip.is_loopback or ip.is_link_local


def is_synthetic_patient_id(patient_hash: str | None) -> bool:
    """合成病例判定：开发形态下唯一被允许出域的患者数据类型。"""
    return bool(patient_hash) and patient_hash.startswith(SYNTHETIC_PATIENT_PREFIX)


class EgressGuard:
    """出域检查器。

    显式传入策略而非读取全局配置，便于测试与多策略共存。
    """

    def __init__(
        self,
        policy: EgressPolicy,
        on_egress: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        Args:
            policy: 出域策略。
            on_egress: 放行回调，用于写审计（`action_type='EGRESS_DEV'`）。
                开发形态下每次放行都必须留痕，因此这里不允许为空——
                未提供时会在首次放行时告警。
        """
        self._policy = policy
        self._on_egress = on_egress
        self._warned_no_audit = False

    @property
    def policy(self) -> EgressPolicy:
        return self._policy

    @property
    def is_sandbox(self) -> bool:
        return self._policy is EgressPolicy.DEV_SANDBOX

    def check(
        self,
        capability: str,
        target_url: str,
        *,
        is_synthetic: bool = False,
    ) -> None:
        """在发起对外请求前调用。不通过则抛异常，请求不得发出。

        Args:
            capability: 能力标识，见模块顶部的三组常量。
            target_url: 目标地址。
            is_synthetic: 本次调用是否只涉及合成数据。
                开发形态下患者链路能力放行的**必要条件**。

        Raises:
            DataResidencyViolation: 判定不通过。

        `dev_sandbox` 下放行需同时满足四项约束（对应 02 文档 §8.2）：

        1. **只允许合成数据** —— 由 `is_synthetic` 参数强制，调用方必须显式声明；
        2. **每次放行都留痕** —— 通过 `on_egress` 回调写审计（`EGRESS_DEV`）；
        3. **必须显式可见** —— 由配置层与接口层负责（启动 WARNING / `egress_policy`
           字段下发 / 前端标识条）；
        4. **交付形态必须拒绝启动** —— 由 `app.config.Settings` 的启动校验负责。
        """
        host = urlparse(target_url).hostname or target_url
        private = is_private_host(host)

        # 院内地址一律放行，无需判定
        if private:
            return

        # ---- 以下均为院外地址 ----

        # 第一道：绝对禁止出域的能力，任何策略都不放行
        if capability in ABSOLUTE_PII_CAPABILITIES:
            raise DataResidencyViolation(
                f"能力 {capability} 涉及患者原始数据，不得访问院外地址：{host}"
            )

        # 第二道：strict 策略下，院外地址一律拒绝，不区分能力
        if self._policy is EgressPolicy.STRICT:
            raise DataResidencyViolation(
                f"strict 策略下禁止访问院外地址：{host}（能力 {capability}）"
            )

        # 第三道：dev_sandbox —— 患者链路能力要求合成数据 + 留痕
        if capability in PATIENT_PIPELINE_CAPABILITIES:
            if not is_synthetic:
                raise DataResidencyViolation(
                    f"dev_sandbox 下能力 {capability} 仅允许合成数据出域，"
                    f"当前调用未标记为合成数据（is_synthetic=False）。\n"
                    f"合成病例的 patient_hash 必须以 {SYNTHETIC_PATIENT_PREFIX!r} 开头。"
                )
            self._record(capability, host)
            return

        # 非患者数据能力（知识库构建、离线向量化、追踪）在开发形态下放行
        self._record(capability, host)

    def _record(self, capability: str, host: str) -> None:
        """开发形态放行留痕。"""
        if self._on_egress is not None:
            self._on_egress(capability, host)
            return
        if not self._warned_no_audit:
            self._warned_no_audit = True
            logger.warning(
                "dev_sandbox 策略下发生出域（能力 %s → %s）但未接入审计回调，"
                "本次放行未被留痕。请为 EgressGuard 注入 on_egress。",
                capability,
                host,
            )
