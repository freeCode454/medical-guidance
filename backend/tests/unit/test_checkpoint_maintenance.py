from __future__ import annotations

import pytest

from app.services.checkpoint_maintenance import purge_finished_threads


class _Scalars:
    def __init__(self, rows: list[str]) -> None:
        self._rows = rows

    def all(self) -> list[str]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[str]) -> None:
        self._rows = rows

    async def scalars(self, *_args, **_kwargs):
        return _Scalars(self._rows)


class _FakeSaver:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)


@pytest.mark.asyncio
async def test_purge_deletes_finished_threads() -> None:
    saver = _FakeSaver()
    result = await purge_finished_threads(_FakeDb(["s1", "s2"]), saver, days=30)
    assert result["eligible"] == 2
    assert result["deleted"] == 2
    assert saver.deleted == ["s1", "s2"]


@pytest.mark.asyncio
async def test_purge_dry_run_keeps_checkpoints() -> None:
    saver = _FakeSaver()
    result = await purge_finished_threads(_FakeDb(["s1"]), saver, days=7, dry_run=True)
    assert result["eligible"] == 1
    assert result["deleted"] == 0
    assert saver.deleted == []


@pytest.mark.asyncio
async def test_purge_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        await purge_finished_threads(_FakeDb([]), _FakeSaver(), days=0)
    with pytest.raises(ValueError):
        await purge_finished_threads(_FakeDb([]), _FakeSaver(), limit=0)
