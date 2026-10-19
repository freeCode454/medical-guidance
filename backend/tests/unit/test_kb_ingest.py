from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.common.exceptions import BizError
from app.services.kb_ingest import rebuild_dept_vectors


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
