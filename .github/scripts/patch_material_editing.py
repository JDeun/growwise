from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/growwise/domain/models.py",
    "    parent_material_id: UUID | None = None\n",
    "    parent_material_id: UUID | None = None\n"
    "    version_note: str | None = None\n",
)

replace_once(
    "src/growwise/generators/__init__.py",
    "from .material import MaterialDraft, MaterialGenerationService\n",
    "from .editing import MaterialEditError, MaterialEditService\n"
    "from .material import MaterialDraft, MaterialGenerationService\n",
)
replace_once(
    "src/growwise/generators/__init__.py",
    '    "MaterialDraft",\n',
    '    "MaterialEditError",\n'
    '    "MaterialEditService",\n'
    '    "MaterialDraft",\n',
)

replace_once(
    "src/growwise/api/main.py",
    "from growwise.generators import (\n"
    "    MaterialGenerationService,\n",
    "from growwise.generators import (\n"
    "    MaterialEditError,\n"
    "    MaterialEditService,\n"
    "    MaterialGenerationService,\n",
)
replace_once(
    "src/growwise/api/main.py",
    "class MaterialRevisionRequest(BaseModel):\n"
    "    note: str | None = Field(default=None, max_length=2000)\n",
    "class MaterialRevisionRequest(BaseModel):\n"
    "    note: str | None = Field(default=None, max_length=2000)\n\n\n"
    "class MaterialEditRequest(BaseModel):\n"
    "    title: str = Field(min_length=1, max_length=500)\n"
    "    content_markdown: str = Field(min_length=1, max_length=100_000)\n"
    "    note: str | None = Field(default=None, max_length=2000)\n",
)

edit_route = '''\n\n@app.post("/v1/materials/{material_id}/edit", response_model=GeneratedMaterial)\ndef edit_material(\n    material_id: UUID,\n    request: MaterialEditRequest,\n    store: Annotated[EntityStore, Depends(get_store)],\n) -> GeneratedMaterial:\n    payload = store.index.get_entity(str(material_id), entity_type="generated_material")\n    if payload is None:\n        raise HTTPException(status_code=404, detail="material_not_found")\n    material = GeneratedMaterial.model_validate(payload)\n\n    versions = store.index.list_entities(\n        entity_type="generated_material",\n        child_id=str(material.child_id),\n    )\n    if any(candidate.get("parent_material_id") == str(material.id) for candidate in versions):\n        raise HTTPException(status_code=409, detail="material_has_newer_version")\n\n    try:\n        edited = MaterialEditService().create_version(\n            material=material,\n            title=request.title,\n            content_markdown=request.content_markdown,\n            note=request.note,\n        )\n    except MaterialEditError as exc:\n        raise HTTPException(status_code=409, detail=str(exc)) from exc\n\n    store.save(edited)\n    review_config = {\n        "configurable": {"thread_id": f"material-review:{edited.id}"}\n    }\n    get_material_review_graph().invoke(\n        {\n            "material_id": str(edited.id),\n            "child_id": str(edited.child_id),\n            "title": edited.title,\n        },\n        config=review_config,\n    )\n    return edited\n'''
replace_once(
    "src/growwise/api/main.py",
    "\n@app.post(\"/v1/observations\", response_model=LearningLog)\ndef create_observation(\n",
    edit_route
    + "\n\n@app.post(\"/v1/observations\", response_model=LearningLog)\ndef create_observation(\n",
)
