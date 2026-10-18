import pytest

from app.common.exceptions import BizError
from app.services import kb_service


class _Entry:
    def __init__(self, code: str, content: str) -> None:
        self.entry_code = code
        self.content = content
        self.status = "0"


class _Scalars:
    def __init__(self, rows: list[_Entry]) -> None:
        self._rows = rows

    def all(self) -> list[_Entry]:
        return self._rows


class _FakeDb:
    def __init__(self, entries: list[_Entry]) -> None:
        self.entries = entries
        self.added: object | None = None
        self.committed = False

    async def scalar(self, *_args):
        return None

    async def scalars(self, *_args):
        return _Scalars(self.entries)

    def add(self, obj: object) -> None:
        self.added = obj

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_publish_marks_active_entries_and_counts_them() -> None:
    entries = [_Entry("DEPT-DIG", "消化内科"), _Entry("GUIDE-1", "指南")]
    db = _FakeDb(entries)

    result = await kb_service.publish_kb(
        db,  # type: ignore[arg-type]
        tenant_id="t1",
        actor_id="u1",
        version_tag="v-test",
    )

    assert result["entry_count"] == 2
    assert result["version_tag"] == "v-test"
    assert result["snapshot_hash"]
    assert all(entry.status == "1" for entry in entries)
    assert db.committed is True


@pytest.mark.asyncio
async def test_publish_rejects_empty_active_set() -> None:
    db = _FakeDb([])
    with pytest.raises(BizError):
        await kb_service.publish_kb(
            db,  # type: ignore[arg-type]
            tenant_id="t1",
            actor_id="u1",
            version_tag="v-empty",
        )
