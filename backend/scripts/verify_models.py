"""校验 SQLAlchemy 模型与 init.sql 逐列一致。

在 backend 目录下执行：
    python scripts/verify_models.py

比对维度：表名集合、每张表的列名集合、每列的类型（归一化后）与可空性。
init.sql 的 char(n) 与模型的 String(n)（varchar(n)）在单字符场景下功能等价，
统一归一化为 varchar(n) 后比较。

返回码：0 表示完全一致；1 表示存在差异（差异明细打印到 stdout）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Base  # noqa: E402

INIT_SQL = BACKEND_DIR.parent / "deploy" / "postgres" / "init.sql"

# 列定义：列名 + 类型（varchar/char/text/integer/bigint/numeric/date/timestamptz/jsonb，可带 []）
_TYPE_RE = re.compile(
    r"(varchar\(\d+\)|char\(\d+\)|text|integer|bigint|numeric\(\d+,\d+\)|date|timestamptz|jsonb)(\[\])?"
)


def normalize_pg_type(t: str) -> str:
    """归一化 init.sql 的 PostgreSQL 类型。char(n) 与 varchar(n) 视为等价。"""
    t = t.strip().lower()
    m = re.match(r"^(varchar|char)\((\d+)\)\[\]$", t)
    if m:
        return f"varchar[{m.group(2)}]"
    m = re.match(r"^(varchar|char)\((\d+)\)$", t)
    if m:
        return f"varchar({m.group(2)})"
    if t == "timestamptz" or t == "timestamp with time zone":
        return "timestamptz"
    return t


def normalize_sa_type(col) -> str:
    """归一化 SQLAlchemy 列类型为与 normalize_pg_type 相同的口径。"""
    t = col.type
    if isinstance(t, String):
        return f"varchar({t.length})" if t.length else "text"
    if isinstance(t, ARRAY):
        inner = t.item_type
        if isinstance(inner, String):
            return f"varchar[{inner.length}]"
        return f"array[{inner}]"
    if isinstance(t, Text):
        return "text"
    if isinstance(t, BigInteger):
        return "bigint"
    if isinstance(t, Integer):
        return "integer"
    if isinstance(t, Numeric):
        return f"numeric({t.precision},{t.scale})"
    if isinstance(t, DateTime):
        return "timestamptz"
    if isinstance(t, Date):
        return "date"
    if isinstance(t, JSONB):
        return "jsonb"
    return str(t)


def parse_init_sql(path: Path) -> dict[str, dict[str, dict]]:
    """解析 init.sql，返回 {表名: {列名: {"type": str, "notnull": bool}}}。"""
    text = path.read_text(encoding="utf-8")
    tables: dict[str, dict[str, dict]] = {}
    pattern = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\);", re.S)
    for m in pattern.finditer(text):
        tname = m.group(1)
        body = m.group(2)
        cols: dict[str, dict] = {}
        for raw in body.split("\n"):
            line = raw.strip().rstrip(",").strip()
            if not line or line.upper().startswith("CONSTRAINT"):
                continue
            cm = re.match(r"^(\w+)\s+(.+)$", line)
            if not cm:
                continue
            col_name, rest = cm.group(1), cm.group(2)
            tm = _TYPE_RE.match(rest)
            if not tm:
                continue
            col_type = tm.group(0)
            notnull = "NOT NULL" in rest.upper()
            cols[col_name] = {"type": normalize_pg_type(col_type), "notnull": notnull}
        tables[tname] = cols
    return tables


def main() -> int:
    pg = parse_init_sql(INIT_SQL)
    sa = {
        tname: {
            c.name: {"type": normalize_sa_type(c), "notnull": not c.nullable}
            for c in Base.metadata.tables[tname].columns
        }
        for tname in Base.metadata.tables
    }

    errors: list[str] = []
    # 表名集合
    pg_tables, sa_tables = set(pg), set(sa)
    for t in sorted(pg_tables - sa_tables):
        errors.append(f"[缺表] init.sql 有 {t}，模型未定义")
    for t in sorted(sa_tables - pg_tables):
        errors.append(f"[多表] 模型有 {t}，init.sql 未定义")

    # 逐表逐列
    for t in sorted(pg_tables & sa_tables):
        pg_cols, sa_cols = pg[t], sa[t]
        for c in sorted(pg_cols.keys() - sa_cols.keys()):
            errors.append(f"[缺列] {t}.{c} 在 init.sql 有，模型缺")
        for c in sorted(sa_cols.keys() - pg_cols.keys()):
            errors.append(f"[多列] {t}.{c} 在模型有，init.sql 缺")
        for c in sorted(pg_cols.keys() & sa_cols.keys()):
            if pg_cols[c]["type"] != sa_cols[c]["type"]:
                errors.append(
                    f"[类型] {t}.{c}: init.sql={pg_cols[c]['type']} 模型={sa_cols[c]['type']}"
                )
            if pg_cols[c]["notnull"] != sa_cols[c]["notnull"]:
                errors.append(
                    f"[可空] {t}.{c}: init.sql notnull={pg_cols[c]['notnull']} "
                    f"模型 notnull={sa_cols[c]['notnull']}"
                )

    print("=" * 64)
    print(f"init.sql 表数：{len(pg_tables)}   模型表数：{len(sa_tables)}")
    print(f"init.sql 列数：{sum(len(v) for v in pg.values())}   "
          f"模型列数：{sum(len(v) for v in sa.values())}")
    print(f"差异数：{len(errors)}")
    print("=" * 64)
    if errors:
        for e in errors:
            print("  " + e)
        print("=" * 64)
        print("结果：不一致 ✗")
        return 1
    print("结果：23 张表逐列完全一致 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
