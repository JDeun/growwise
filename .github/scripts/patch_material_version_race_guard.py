from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/growwise/api/main.py",
    "from growwise.model import ModelProvider, create_model_provider\n",
    "from growwise.material_versions import serialize_material_successor\n"
    "from growwise.model import ModelProvider, create_model_provider\n",
)
replace_once(
    "src/growwise/api/main.py",
    '@app.post("/v1/materials/{material_id}/revise", response_model=GeneratedMaterial)\n'
    "def revise_material(\n",
    '@app.post("/v1/materials/{material_id}/revise", response_model=GeneratedMaterial)\n'
    "@serialize_material_successor\n"
    "def revise_material(\n",
)
replace_once(
    "src/growwise/api/main.py",
    '@app.post("/v1/materials/{material_id}/edit", response_model=GeneratedMaterial)\n'
    "def edit_material(\n",
    '@app.post("/v1/materials/{material_id}/edit", response_model=GeneratedMaterial)\n'
    "@serialize_material_successor\n"
    "def edit_material(\n",
)
