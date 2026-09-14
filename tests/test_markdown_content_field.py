from growwise.domain import ResourceKind, ResourceRecord
from growwise.storage import MarkdownRepository, SQLiteProjection


def test_markdown_repository_supports_content_named_field(tmp_path) -> None:
    records = tmp_path / "records"
    repository = MarkdownRepository(records)
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="테스트 자료",
        content="본문 데이터",
    )

    path = repository.save(resource)
    loaded = repository.load(path, ResourceRecord)

    assert loaded.id == resource.id
    assert loaded.content == "본문 데이터"

    projection = SQLiteProjection(tmp_path / "rebuilt.sqlite3")
    assert projection.rebuild(records) == 1
    rebuilt = projection.get_entity(str(resource.id), entity_type="resource")
    assert rebuilt is not None
    assert rebuilt["content"] == "본문 데이터"
    assert "__growwise_content" not in rebuilt
