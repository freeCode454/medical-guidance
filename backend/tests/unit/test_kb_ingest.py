from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.common.exceptions import BizError
from app.services.kb_ingest import _row_for, rebuild_dept_vectors


class _Scalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    async def scalars(self, *_args, **_kwargs):
        return _Scalars(self._rows)


class _Embedder:
    async def embed(self, texts: list[str]):
        return [SimpleNamespace(dense=[0.1, 0.2], sparse={1: 0.5}) for _ in texts]


class _Store:
    def __init__(self) -> None:
        self.upserted: list[dict] = []
        self.deleted: list[str] = []
        self.flushed = 0

    def upsert(self, _spec, rows):
        self.upserted = rows

    def list_ids(self, _spec, _filter):
        return ["dept_DIG", "dept_OLD"]

    def delete(self, _spec, ids):
        self.deleted = ids

    def flush(self, _spec):
        self.flushed += 1


def _entry(code: str, title: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        dept_code=code, title=title, content=content, entry_code=f"DEPT-{code}"
    )


@pytest.mark.asyncio
async def test_rebuild_upserts_active_and_deletes_stale() -> None:
    store = _Store()
    result = await rebuild_dept_vectors(
        _FakeDb([_entry("DIG", "消化内科", "腹痛腹泻")]),  # type: ignore[arg-type]
        tenant_id="t1",
        embedder=_Embedder(),
        store=store,
    )
    assert result == {"total": 1, "upserted": 1, "deleted": 1}
    assert store.upserted[0]["id"] == "dept_DIG"
    assert store.upserted[0]["dept_name"] == "消化内科"
    assert store.deleted == ["dept_OLD"]
    assert store.flushed == 1


@pytest.mark.asyncio
async def test_rebuild_rejects_empty_active_set() -> None:
    with pytest.raises(BizError):
        await rebuild_dept_vectors(
            _FakeDb([]),  # type: ignore[arg-type]
            tenant_id="t1",
            embedder=_Embedder(),
            store=_Store(),
        )


def test_row_mapping_for_all_collections() -> None:
    entry = SimpleNamespace(
        id="a" * 32,
        dept_code="DIG",
        title="急性胃肠炎",
        content="腹痛腹泻",
        icd10_codes=["A09.9"],
        age_group="adult",
        gender="1",
        content_json={
            "evidence_level": "A",
            "year": 2021,
            "chapter": "第十一章",
            "drug_name": "阿莫西林",
            "severity": "HIGH",
        },
    )
    emb = SimpleNamespace(dense=[0.1], sparse={1: 0.2})

    dept = _row_for("dept", entry, "text", emb, "t1")
    assert dept["id"] == "dept_DIG"
    assert dept["dept_name"] == "急性胃肠炎"

    symptom = _row_for("symptom", entry, "text", emb, "t1")
    assert symptom["icd10_code"] == "A09.9"
    assert symptom["age_group"] == "adult"

    guideline = _row_for("guideline", entry, "text", emb, "t1")
    assert guideline["evidence_level"] == "A"
    assert guideline["pub_year"] == "2021"

    icd = _row_for("icd10", entry, "text", emb, "t1")
    assert "tenant_id" not in icd
    assert icd["chapter"] == "第十一章"

    drug = _row_for("drug", entry, "text", emb, "t1")
    assert drug["drug_name"] == "阿莫西林"
    assert drug["taboo_type"] == "HIGH"

    case = _row_for("case", entry, "text", emb, "t1")
    assert case["dept_code"] == "DIG"
