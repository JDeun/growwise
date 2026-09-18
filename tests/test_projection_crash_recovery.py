from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore

_CHILD_ID = "11111111-2222-4333-8444-555555555555"


def test_projection_recovers_after_process_exit_between_markdown_and_index(tmp_path: Path) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    script = r"""
import os
from pathlib import Path
from uuid import UUID

from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore

records = Path(os.environ["GROWWISE_TEST_RECORDS"])
index = Path(os.environ["GROWWISE_TEST_INDEX"])
store = EntityStore(records, index)

def hard_exit(*_args, **_kwargs):
    os._exit(86)

store.index.upsert = hard_exit
store.save(
    ChildProfile(
        id=UUID(os.environ["GROWWISE_TEST_CHILD_ID"]),
        nickname="crash-child",
        stage=Stage.ELEMENTARY,
    )
)
"""
    env = dict(os.environ)
    env.update(
        {
            "GROWWISE_TEST_RECORDS": str(records),
            "GROWWISE_TEST_INDEX": str(index),
            "GROWWISE_TEST_CHILD_ID": _CHILD_ID,
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env,
        check=False,
        timeout=30,
    )

    assert result.returncode == 86
    dirty = index.with_name(f"{index.name}.dirty")
    assert dirty.is_file()

    # The authoritative Markdown commit survived the hard exit, while the incremental projection
    # write did not. A new process/store must detect the durable marker and rebuild automatically.
    recovered = EntityStore(records, index)
    payload = recovered.index.get_entity(_CHILD_ID, entity_type="child_profile")

    assert payload is not None
    assert payload["nickname"] == "crash-child"
    assert not dirty.exists()


def test_dirty_marker_stays_until_all_concurrent_mutations_finish(tmp_path: Path) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    first = EntityStore(records, index)
    second = EntityStore(records, index)
    dirty = index.with_name(f"{index.name}.dirty")

    first._mark_projection_dirty()
    second._mark_projection_dirty()
    assert dirty.exists()

    first._clear_projection_dirty()
    assert dirty.exists()

    second._clear_projection_dirty()
    assert not dirty.exists()


def test_failed_concurrent_mutation_cannot_let_successful_peer_clear_recovery_marker(
    tmp_path: Path,
) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    first = EntityStore(records, index)
    second = EntityStore(records, index)
    dirty = index.with_name(f"{index.name}.dirty")

    first._mark_projection_dirty()
    second._mark_projection_dirty()
    first._abandon_projection_dirty()
    second._clear_projection_dirty()

    assert dirty.exists()

    # A fresh store is allowed to recover only after no process-local mutation lease remains.
    EntityStore(records, index)
    assert not dirty.exists()


def test_dirty_marker_recovery_rebuilds_stale_projection_from_markdown(tmp_path: Path) -> None:
    records = tmp_path / "records"
    index = tmp_path / "index.sqlite3"
    store = EntityStore(records, index)
    child = ChildProfile(
        id=_CHILD_ID,
        nickname="before",
        stage=Stage.ELEMENTARY,
    )
    store.save(child)

    child.nickname = "after"
    rendered = store.markdown.render(child)
    path = store.markdown.path_for(child)
    with store.markdown.lock_for(path):
        store.markdown._write_locked(path, rendered)

    # Simulate a crash after authoritative source replacement but before projection upsert.
    dirty = index.with_name(f"{index.name}.dirty")
    dirty.write_bytes(b"dirty\n")
    stale = store.index.get_entity(_CHILD_ID, entity_type="child_profile")
    assert stale is not None
    assert stale["nickname"] == "before"

    rebuilt = EntityStore(records, index)
    fresh = rebuilt.index.get_entity(_CHILD_ID, entity_type="child_profile")
    assert fresh is not None
    assert fresh["nickname"] == "after"
    assert not dirty.exists()
