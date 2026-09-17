from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import frontmatter
import pytest

from growwise.backup import BackupService, InvalidBackup
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.storage.markdown import MarkdownRepository


def _manifest(record_count: int) -> str:
    return json.dumps(
        {
            "format_version": 1,
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "record_count": record_count,
        }
    )


def _restore_archive(tmp_path: Path, members: dict[str, str]) -> None:
    archive = tmp_path / "semantic.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", _manifest(len(members)))
        for name, content in members.items():
            output.writestr(name, content)

    BackupService().restore(
        archive_path=archive,
        records_root=tmp_path / "restored-records",
        index_path=tmp_path / "restored.sqlite3",
    )


def _render(tmp_path: Path, entity: ChildProfile | ResourceRecord) -> str:
    return MarkdownRepository(tmp_path / "render").render(entity)


def test_restore_rejects_entity_type_directory_mismatch(tmp_path: Path) -> None:
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=10)
    content = _render(tmp_path, child)

    with pytest.raises(InvalidBackup, match="entity_type does not match"):
        _restore_archive(
            tmp_path,
            {f"records/resource/{child.id}.md": content},
        )


def test_restore_rejects_filename_id_mismatch(tmp_path: Path) -> None:
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=10)
    content = _render(tmp_path, child)

    with pytest.raises(InvalidBackup, match="id does not match its filename"):
        _restore_archive(
            tmp_path,
            {f"records/child_profile/{uuid4()}.md": content},
        )


def test_restore_rejects_duplicate_ids_across_entity_types(tmp_path: Path) -> None:
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=10)
    resource = ResourceRecord(
        id=child.id,
        kind=ResourceKind.NOTE,
        title="중복 UUID 자료",
        content="duplicate identity",
    )

    with pytest.raises(InvalidBackup, match="duplicate record id"):
        _restore_archive(
            tmp_path,
            {
                f"records/child_profile/{child.id}.md": _render(tmp_path, child),
                f"records/resource/{resource.id}.md": _render(tmp_path, resource),
            },
        )


def test_restore_rejects_payload_that_fails_concrete_domain_model(tmp_path: Path) -> None:
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=10)
    post = frontmatter.loads(_render(tmp_path, child))
    post.metadata["stage"] = "not-a-real-stage"
    malformed = frontmatter.dumps(post)

    with pytest.raises(InvalidBackup, match="ChildProfile validation"):
        _restore_archive(
            tmp_path,
            {f"records/child_profile/{child.id}.md": malformed},
        )
