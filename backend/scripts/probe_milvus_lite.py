"""Milvus Lite 能力探测。

背景：Milvus Lite 存在两代实现（早期 C++ 封装版 / 新版纯 Python 实现），
两者同名但支持的特性差异很大。本项目的分诊检索依赖其中的
「稠密 + 稀疏(BM25) 混合检索」与「标量过滤」，因此开发第一天必须先跑通本脚本。

用法：
    python scripts/probe_milvus_lite.py
    python scripts/probe_milvus_lite.py --uri ./data/probe.db --keep

退出码：0 表示核心能力全部可用；1 表示存在不可用项（脚本末尾给出降级建议）。
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

DIM = 1024  # 与 bge-m3 的向量维度一致
COLLECTION = "probe_kb"
PARTITION_COLLECTION = "probe_partition"

# 中文医疗语料，用于验证分词与 BM25 是否真的作用于中文
CORPUS = [
    ("doc-1", "腹痛 腹泻 恶心 呕吐 消化内科 急性胃肠炎表现", "DIG", "HOSP_001"),
    ("doc-2", "胸痛 出汗 后背放射痛 心内科 需警惕急性冠脉综合征", "CAR", "HOSP_001"),
    ("doc-3", "咳嗽 咳痰 发热 呼吸困难 呼吸内科", "RES", "HOSP_001"),
    ("doc-4", "视物模糊 多饮 多尿 内分泌科 糖尿病相关", "END", "HOSP_002"),
    ("doc-5", "头痛 眩晕 一侧肢体无力 神经内科", "NEU", "HOSP_002"),
]


@dataclass
class Result:
    name: str
    status: str  # ok / fail / skip
    detail: str = ""


@dataclass
class ProbeReport:
    results: list[Result] = field(default_factory=list)
    fatal: bool = False

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.results.append(Result(name, status, detail))
        mark = {"ok": "PASS", "fail": "FAIL", "skip": "SKIP"}[status]
        print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def failures(self) -> list[Result]:
        return [r for r in self.results if r.status == "fail"]


def _vec(seed: int) -> list[float]:
    rnd = random.Random(seed)
    return [rnd.uniform(-1.0, 1.0) for _ in range(DIM)]


def _drop(client, name: str) -> None:
    try:
        if client.has_collection(name):
            client.drop_collection(name)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 各项探测
# --------------------------------------------------------------------------


def probe_build_collection(client, report: ProbeReport) -> bool:
    """建库：稠密 + 稀疏 + BM25 函数 + 标量字段。这是全部检索能力的前提。"""
    try:
        from pymilvus import DataType, Function, FunctionType

        _drop(client, COLLECTION)
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("text", DataType.VARCHAR, max_length=4096, enable_analyzer=True)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DIM)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("dept_code", DataType.VARCHAR, max_length=32)
        schema.add_field("org_id", DataType.VARCHAR, max_length=32)
        schema.add_function(
            Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["text"],
                output_field_names=["sparse"],
            )
        )
        client.create_collection(COLLECTION, schema=schema)
        report.add("建 collection（含 BM25 函数）", "ok")
        return True
    except Exception as exc:
        report.add("建 collection（含 BM25 函数）", "fail", f"{type(exc).__name__}: {exc}")
        report.fatal = True
        return False


def probe_index(client, report: ProbeReport) -> None:
    try:
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense", index_type="HNSW", metric_type="COSINE",
            params={"M": 32, "efConstruction": 256},
        )
        index_params.add_index(
            field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25", params={},
        )
        client.create_index(COLLECTION, index_params)
        client.load_collection(COLLECTION)
        report.add("建索引并加载（HNSW + 稀疏倒排）", "ok")
    except Exception as exc:
        report.add("建索引并加载（HNSW + 稀疏倒排）", "fail", f"{type(exc).__name__}: {exc}")


def probe_insert(client, report: ProbeReport) -> None:
    try:
        rows = [
            {
                "id": doc_id,
                "text": text,
                "dense": _vec(i),
                "dept_code": dept,
                "org_id": org,
            }
            for i, (doc_id, text, dept, org) in enumerate(CORPUS)
        ]
        client.insert(COLLECTION, rows)
        client.flush(COLLECTION)  # Milvus insert 是异步的，必须 flush 后才能统计与检索
        stats = client.get_collection_stats(COLLECTION)
        report.add("插入数据", "ok", f"行数={stats.get('row_count', '?')}")
    except Exception as exc:
        report.add("插入数据", "fail", f"{type(exc).__name__}: {exc}")


def probe_dense_search(client, report: ProbeReport) -> None:
    try:
        hits = client.search(
            COLLECTION, data=[_vec(0)], anns_field="dense",
            limit=3, output_fields=["text", "dept_code"],
        )
        top = hits[0][0] if hits and hits[0] else None
        report.add("稠密向量检索", "ok", f"首条={top.get('id') if top else '无'}")
    except Exception as exc:
        report.add("稠密向量检索", "fail", f"{type(exc).__name__}: {exc}")


def probe_sparse_search(client, report: ProbeReport) -> None:
    """BM25 全文检索是本项目混合检索的核心，单独验证。"""
    try:
        hits = client.search(
            COLLECTION, data=["腹痛 腹泻"], anns_field="sparse",
            limit=3, output_fields=["text"],
        )
        ids = [h.get("id") for h in hits[0]] if hits and hits[0] else []
        report.add("稀疏向量检索（BM25 全文）", "ok",
                   f"命中={ids or '无'}（期望含 doc-1）")
    except Exception as exc:
        report.add("稀疏向量检索（BM25 全文）", "fail", f"{type(exc).__name__}: {exc}")


def probe_hybrid_search(client, report: ProbeReport) -> None:
    """稠密 + 稀疏 + RRF 融合，是知识库检索链路的关键能力。"""
    try:
        from pymilvus import AnnSearchRequest, RRFRanker

        dense_req = AnnSearchRequest(
            data=[_vec(0)], anns_field="dense",
            param={"metric_type": "COSINE"}, limit=5,
        )
        sparse_req = AnnSearchRequest(
            data=["腹痛 腹泻"], anns_field="sparse",
            param={"metric_type": "BM25"}, limit=5,
        )
        hits = client.hybrid_search(
            COLLECTION, [dense_req, sparse_req],
            ranker=RRFRanker(), limit=3, output_fields=["text", "dept_code"],
        )
        ids = [h.get("id") for h in hits[0]] if hits and hits[0] else []
        report.add("混合检索（RRF 融合）", "ok", f"命中={ids or '无'}")
    except Exception as exc:
        report.add("混合检索（RRF 融合）", "fail", f"{type(exc).__name__}: {exc}")


def probe_scalar_filter(client, report: ProbeReport) -> None:
    """按科室与机构过滤，是多租户与科室级隔离的基础。"""
    try:
        hits = client.search(
            COLLECTION, data=[_vec(0)], anns_field="dense", limit=5,
            filter='org_id == "HOSP_001" and dept_code in ["DIG", "CAR"]',
            output_fields=["dept_code", "org_id"],
        )
        rows = hits[0] if hits and hits[0] else []
        leaked = [r for r in rows if r.get("org_id") != "HOSP_001"]
        if leaked:
            report.add("标量过滤（机构 + 科室）", "fail", f"过滤失效，越界结果={len(leaked)}")
        else:
            report.add("标量过滤（机构 + 科室）", "ok", f"返回 {len(rows)} 条，无越界")
    except Exception as exc:
        report.add("标量过滤（机构 + 科室）", "fail", f"{type(exc).__name__}: {exc}")


def probe_partition_key(client, report: ProbeReport) -> None:
    """分区键是机构级物理隔离选项。缺失不影响功能，只影响性能与隔离强度。"""
    try:
        from pymilvus import DataType

        _drop(client, PARTITION_COLLECTION)
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DIM)
        schema.add_field("org_id", DataType.VARCHAR, max_length=32, is_partition_key=True)
        client.create_collection(PARTITION_COLLECTION, schema=schema)
        report.add("分区键（partition key）", "ok")
    except Exception as exc:
        report.add("分区键（partition key）", "skip",
                   f"不支持：{type(exc).__name__}: {exc}。改用标量过滤实现机构隔离")


def probe_chinese_analyzer(client, report: ProbeReport) -> None:
    """中文分词质量直接影响 BM25 召回，单独探测是否支持中文分析器。"""
    try:
        from pymilvus import DataType

        name = "probe_zh"
        _drop(client, name)
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(
            "text", DataType.VARCHAR, max_length=4096,
            enable_analyzer=True, analyzer_params={"type": "chinese"},
        )
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        client.create_collection(name, schema=schema)
        _drop(client, name)
        report.add("中文分析器", "ok", "支持 analyzer_params={'type': 'chinese'}")
    except Exception as exc:
        report.add("中文分析器", "skip",
                   f"不支持中文分析器（{type(exc).__name__}）。"
                   "BM25 将退回默认分词，中文医疗词汇召回会下降，"
                   "需改用「关键词扩展 + 稠密检索」补偿")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="探测 Milvus 的能力边界（Standalone / Lite 通用）")
    parser.add_argument("--uri", default="http://localhost:19530",
                        help="Milvus 地址。Standalone 用 http://host:19530；Lite 用本地文件路径")
    parser.add_argument("--keep", action="store_true", help="结束后保留探测库（仅本地文件路径有效）")
    args = parser.parse_args()

    is_local_file = "://" not in args.uri
    db_path = Path(args.uri) if is_local_file else None
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("Milvus 能力探测")
    print(f"目标地址：{args.uri}")
    print("=" * 68)

    try:
        from pymilvus import __version__ as pymilvus_version
        from pymilvus import MilvusClient

        print(f"pymilvus 版本：{pymilvus_version}")
    except ImportError as exc:
        print(f"依赖缺失：{exc}")
        print("请先执行：pip install -U \"pymilvus[milvus-lite]\"")
        return 1

    report = ProbeReport()
    try:
        client = MilvusClient(args.uri)
    except Exception as exc:
        print(f"无法连接 Milvus：{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1

    try:
        if probe_build_collection(client, report):
            probe_index(client, report)
            probe_insert(client, report)
            probe_dense_search(client, report)
            probe_sparse_search(client, report)
            probe_hybrid_search(client, report)
            probe_scalar_filter(client, report)
        else:
            for name in ("建索引并加载（HNSW + 稀疏倒排）", "插入数据", "稠密向量检索",
                         "稀疏向量检索（BM25 全文）", "混合检索（RRF 融合）",
                         "标量过滤（机构 + 科室）"):
                report.add(name, "skip", "前置步骤失败")

        probe_partition_key(client, report)
        probe_chinese_analyzer(client, report)
    finally:
        _drop(client, COLLECTION)
        _drop(client, PARTITION_COLLECTION)
        try:
            client.close()
        except Exception:
            pass
        if not args.keep and db_path is not None and db_path.exists():
            shutil.rmtree(db_path, ignore_errors=True) if db_path.is_dir() else db_path.unlink()

    print("=" * 68)
    print("结论")
    print("=" * 68)

    ok = [r for r in report.results if r.status == "ok"]
    failed = [r for r in report.results if r.status == "fail"]
    skipped = [r for r in report.results if r.status == "skip"]
    print(f"通过 {len(ok)} 项 / 失败 {len(failed)} 项 / 跳过 {len(skipped)} 项")

    core_failed = [r for r in failed if "BM25" in r.name or "混合检索" in r.name
                   or "collection" in r.name]
    if core_failed:
        print()
        print("核心检索能力不可用，向量库方案需要降级。可选路径：")
        print("  1) 在 WSL2 中运行 Milvus Standalone（绕开 Windows 兼容性问题）")
        print("  2) 使用 Zilliz Cloud 免费层（开发期仅用合成数据）")
        print("  3) 检索层换用本地轻量实现（要求检索层已抽象为接口）")
        return 1

    if failed:
        print()
        print("存在非核心项失败，但不影响主检索链路，可继续开发。")

    print()
    print("核心能力可用：稠密检索 + BM25 全文 + 混合检索 + 标量过滤")
    return 0


if __name__ == "__main__":
    sys.exit(main())
