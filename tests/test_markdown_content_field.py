from growwise.domain import ResourceKind, ResourceRecord
from growwise.storage import MarkdownRepository


def test_markdown_repository_supports_content_named_field(tmp_path) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    resource = ResourceRecord(
        kind=ResourceKind.NOTE,
        title="테스트 자료",
        content="본문 데이터",
    )

    path = repository.save(resource)
    loaded = repository.load(path, ResourceRecord)

    assert loaded.id == resource.id
    assert loaded.content == "본문 데이터"
