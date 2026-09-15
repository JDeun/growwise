from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected snippet not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


helper = '''\n\ndef validate_material_source_refs(\n    *,\n    child_id: UUID,\n    source_refs: list[str],\n    store: EntityStore,\n) -> list[str]:\n    """Resolve material provenance to existing resources within the child's scope."""\n    validated: list[str] = []\n    for ref in dict.fromkeys(source_refs):\n        if not ref.startswith("resource:"):\n            raise HTTPException(status_code=422, detail="material_source_ref_invalid")\n        raw_id = ref.removeprefix("resource:")\n        try:\n            resource_id = UUID(raw_id)\n        except ValueError as exc:\n            raise HTTPException(\n                status_code=422, detail="material_source_ref_invalid"\n            ) from exc\n        payload = store.index.get_entity(str(resource_id), entity_type="resource")\n        if payload is None:\n            raise HTTPException(status_code=422, detail="material_source_not_found")\n        resource = ResourceRecord.model_validate(payload)\n        if resource.child_id is not None and resource.child_id != child_id:\n            raise HTTPException(status_code=409, detail="material_source_child_mismatch")\n        validated.append(f"resource:{resource.id}")\n    return validated\n'''

replace_once(
    "src/growwise/api/main.py",
    '''\n@app.post("/v1/children/{child_id}/materials", response_model=GeneratedMaterial)\ndef generate_material(\n''',
    helper + '''\n\n@app.post("/v1/children/{child_id}/materials", response_model=GeneratedMaterial)\ndef generate_material(\n''',
)
replace_once(
    "src/growwise/api/main.py",
    '''    child = ChildProfile.model_validate(child_payload)\n    material = MaterialGenerationService(provider=get_model_provider()).generate(\n        child=child,\n        kind=request.kind,\n        topic=request.topic,\n        goal=request.goal,\n        source_refs=request.source_refs,\n    )\n''',
    '''    child = ChildProfile.model_validate(child_payload)\n    source_refs = validate_material_source_refs(\n        child_id=child.id,\n        source_refs=request.source_refs,\n        store=store,\n    )\n    material = MaterialGenerationService(provider=get_model_provider()).generate(\n        child=child,\n        kind=request.kind,\n        topic=request.topic,\n        goal=request.goal,\n        source_refs=source_refs,\n    )\n''',
)

# Extend adversarial/API tests with provenance isolation and one complete reading vertical slice.
replace_once(
    "tests/test_material_adversarial.py",
    '''    MaterialGenerateRequest,\n    MaterialReviewRequest,\n    MaterialRevisionRequest,\n)\nfrom growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage\n''',
    '''    MaterialGenerateRequest,\n    MaterialReviewRequest,\n    MaterialRevisionRequest,\n    ResourceCreateRequest,\n)\nfrom growwise.domain import (\n    ChildProfile,\n    MaterialKind,\n    MaterialStatus,\n    ResourceKind,\n    ResourceRecord,\n    Stage,\n)\n''',
)
replace_once(
    "tests/test_material_adversarial.py",
    '''from growwise.generators import MaterialGenerationService\nfrom growwise.review import InvalidMaterialTransition, MaterialReviewService\nfrom growwise.storage import EntityStore\n''',
    '''from growwise.generators import MaterialGenerationService\nfrom growwise.rag import HybridRagIndex\nfrom growwise.review import InvalidMaterialTransition, MaterialReviewService\nfrom growwise.storage import EntityStore\n''',
)

addition = r'''


def test_material_api_rejects_missing_source_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    monkeypatch.setattr(api, "get_model_provider", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        api.generate_material(
            child.id,
            MaterialGenerateRequest(
                kind=MaterialKind.READING_ACTIVITY,
                topic="그림책",
                source_refs=["resource:00000000-0000-0000-0000-000000000001"],
            ),
            store,
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "material_source_not_found"


def test_material_api_rejects_other_child_private_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    other = ChildProfile(nickname="다른 아이", stage=Stage.INFANT_0_2, age_months=12)
    store.save(other)
    private_resource = ResourceRecord(
        child_id=other.id,
        kind=ResourceKind.BOOK,
        title="다른 아이의 책 메모",
        content="private",
    )
    store.save(private_resource)
    monkeypatch.setattr(api, "get_model_provider", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        api.generate_material(
            child.id,
            MaterialGenerateRequest(
                kind=MaterialKind.READING_ACTIVITY,
                topic="그림책",
                source_refs=[f"resource:{private_resource.id}"],
            ),
            store,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "material_source_child_mismatch"


def test_reading_material_vertical_slice_preserves_provenance_through_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    rag_index = HybridRagIndex(tmp_path / "rag.sqlite3")
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)
    monkeypatch.setattr(api, "get_rag_index", lambda: rag_index)

    resource = api.create_resource(
        ResourceCreateRequest(
            child_id=child.id,
            kind=ResourceKind.BOOK,
            title="고양이 그림책 메모",
            content="고양이가 창가에서 새를 바라보는 장면이 있다.",
            source_name="부모 기록",
            provenance={"entered_by": "parent"},
        ),
        store,
    )
    source_ref = f"resource:{resource.id}"

    first = api.generate_material(
        child.id,
        MaterialGenerateRequest(
            kind=MaterialKind.READING_ACTIVITY,
            topic="고양이 그림책",
            goal="장면을 관찰하고 아이의 반응을 기다린다.",
            source_refs=[source_ref],
        ),
        store,
    )
    assert first.status is MaterialStatus.REVIEW_PENDING
    assert first.source_refs == [source_ref]
    assert source_ref in first.content_markdown
    assert MaterialReviewService().can_export(first) is False

    requested = api.review_material(
        first.id,
        MaterialReviewRequest(
            status=MaterialStatus.REVISION_REQUESTED,
            note="질문을 하나로 줄여주세요.",
        ),
        store,
    )
    second = api.revise_material(requested.id, MaterialRevisionRequest(), store)
    assert second.version == 2
    assert second.parent_material_id == first.id
    assert second.source_refs == [source_ref]
    assert second.status is MaterialStatus.REVIEW_PENDING

    approved = api.review_material(
        second.id,
        MaterialReviewRequest(status=MaterialStatus.APPROVED, note="최종 확인"),
        store,
    )
    assert approved.status is MaterialStatus.APPROVED
    assert approved.source_refs == [source_ref]
    assert MaterialReviewService().can_export(approved) is True

    indexed = rag_index.search(query="창가 새", child_id=str(child.id))
    assert indexed
'''

path = Path("tests/test_material_adversarial.py")
text = path.read_text(encoding="utf-8")
if "test_reading_material_vertical_slice_preserves_provenance_through_revision" not in text:
    path.write_text(text + addition, encoding="utf-8")
