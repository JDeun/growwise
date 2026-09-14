from pathlib import Path

api_path = Path("src/growwise/api/main.py")
text = api_path.read_text(encoding="utf-8")

old = "from growwise.generators import MaterialGenerationService\n"
new = """from growwise.generators import (
    MaterialGenerationService,
    MaterialRevisionError,
    MaterialRevisionService,
)
"""
assert old in text
text = text.replace(old, new, 1)

old = """class MaterialReviewRequest(BaseModel):
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


"""
new = old + """class MaterialRevisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


"""
assert old in text
text = text.replace(old, new, 1)

old = """    material = MaterialGenerationService(provider=get_model_provider()).generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=request.source_refs,
    )
    store.save(material)
"""
new = """    material = MaterialGenerationService(provider=get_model_provider()).generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=request.source_refs,
    )
    material.request_topic = request.topic
    material.request_goal = request.goal
    store.save(material)
"""
assert old in text
text = text.replace(old, new, 1)

anchor = '\n\n@app.post("/v1/observations", response_model=LearningLog)\n'
assert anchor in text
endpoint = '''

@app.post("/v1/materials/{material_id}/revise", response_model=GeneratedMaterial)
def revise_material(
    material_id: UUID,
    request: MaterialRevisionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    if material.status is not MaterialStatus.REVISION_REQUESTED:
        raise HTTPException(
            status_code=409,
            detail="material must be revision_requested before regeneration",
        )

    child_payload = store.index.get_entity(str(material.child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=409, detail="material_child_not_found")
    child = ChildProfile.model_validate(child_payload)

    # Revision history is intentionally linear. Retrying the same parent revision must not
    # create sibling versions; the already-persisted child version is the idempotent result.
    existing_revisions = store.index.list_entities(
        entity_type="generated_material",
        child_id=str(material.child_id),
    )
    for candidate in existing_revisions:
        if candidate.get("parent_material_id") == str(material.id):
            return GeneratedMaterial.model_validate(candidate)

    try:
        revised = MaterialRevisionService(
            MaterialGenerationService(provider=get_model_provider())
        ).revise(material=material, child=child, note=request.note)
    except MaterialRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    store.save(revised)
    review_config = {
        "configurable": {"thread_id": f"material-review:{revised.id}"}
    }
    get_material_review_graph().invoke(
        {
            "material_id": str(revised.id),
            "child_id": str(child.id),
            "title": revised.title,
        },
        config=review_config,
    )
    return revised
'''
text = text.replace(anchor, endpoint + anchor, 1)
api_path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_material_adversarial.py")
tests = test_path.read_text(encoding="utf-8")
old = "from growwise.api.main import MaterialGenerateRequest, MaterialReviewRequest\n"
new = """from growwise.api.main import (
    MaterialGenerateRequest,
    MaterialReviewRequest,
    MaterialRevisionRequest,
)
"""
assert old in tests
tests = tests.replace(old, new, 1)
tests += '''


def test_revision_api_preserves_request_lineage_and_is_retry_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)

    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(
            topic="달의 모양",
            goal="관찰한 차이를 말로 설명한다.",
            kind=MaterialKind.SCIENCE_INQUIRY,
        ),
        store,
    )
    assert material.request_topic == "달의 모양"
    assert material.request_goal == "관찰한 차이를 말로 설명한다."

    requested = api.review_material(
        material.id,
        MaterialReviewRequest(
            status=MaterialStatus.REVISION_REQUESTED,
            note="질문 수를 줄이고 관찰 중심으로 바꿔주세요.",
        ),
        store,
    )
    revised = api.revise_material(
        requested.id,
        MaterialRevisionRequest(),
        store,
    )

    assert revised.status is MaterialStatus.REVIEW_PENDING
    assert revised.version == 2
    assert revised.parent_material_id == material.id
    assert revised.request_topic == "달의 모양"
    assert "관찰한 차이를 말로 설명한다." in (revised.request_goal or "")
    assert "질문 수를 줄이고 관찰 중심으로" in (revised.request_goal or "")
    assert graph.calls[-1][1]["configurable"]["thread_id"] == f"material-review:{revised.id}"

    call_count = len(graph.calls)
    retried = api.revise_material(
        requested.id,
        MaterialRevisionRequest(note="재시도에서 다른 버전이 생기면 안 됩니다."),
        store,
    )
    assert retried.id == revised.id
    assert len(graph.calls) == call_count


def test_revision_api_rejects_material_without_revision_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, child = _store_with_child(tmp_path)
    graph = RecordingReviewGraph()
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: graph)
    material = api.generate_material(
        child.id,
        MaterialGenerateRequest(topic="그림자"),
        store,
    )

    with pytest.raises(HTTPException) as exc_info:
        api.revise_material(material.id, MaterialRevisionRequest(), store)
    assert exc_info.value.status_code == 409
'''
test_path.write_text(tests, encoding="utf-8")
