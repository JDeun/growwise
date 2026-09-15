from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "desktop/src/api.ts",
    "version: number; parent_material_id: string | null; created_at?: string; updated_at?: string; }",
    "version: number; parent_material_id: string | null; version_note: string | null; created_at?: string; updated_at?: string; }",
)
replace_once(
    "desktop/src/api.ts",
    'export const reviseMaterial = (materialId: string, note?: string) => call<GeneratedMaterial>("revise_material", { materialId, note: note ?? null });\n',
    'export const reviseMaterial = (materialId: string, note?: string) => call<GeneratedMaterial>("revise_material", { materialId, note: note ?? null });\n'
    'export const editMaterial = (materialId: string, title: string, contentMarkdown: string, note?: string | null) => call<GeneratedMaterial>("edit_material", { materialId, title, contentMarkdown, note: note ?? null });\n',
)

replace_once(
    "desktop/src/App.tsx",
    'import { FormEvent, useCallback, useEffect, useState } from "react";\n\n',
    'import { FormEvent, useCallback, useEffect, useState } from "react";\n\n'
    'import { MaterialEditPanel } from "./MaterialEditPanel";\n',
)
replace_once(
    "desktop/src/App.tsx",
    "  exportBackup,\n  generateMaterial,\n",
    "  exportBackup,\n  editMaterial,\n  generateMaterial,\n",
)
replace_once(
    "desktop/src/App.tsx",
    '  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});\n',
    '  const [revisionNotes, setRevisionNotes] = useState<Record<string, string>>({});\n'
    '  const [editingMaterialId, setEditingMaterialId] = useState<string | null>(null);\n',
)
replace_once(
    "desktop/src/App.tsx",
    "  async function handleLoadActivities() {\n",
    '''  async function handleParentEdit(
    materialId: string,
    title: string,
    contentMarkdown: string,
    note: string | null,
  ) {
    if (!activeChild) return;
    setMaterialBusy(true);
    setMaterialError(null);
    try {
      await editMaterial(materialId, title, contentMarkdown, note);
      setMaterials(await listMaterials(activeChild.id));
      setEditingMaterialId(null);
    } catch (error) {
      setMaterialError(error instanceof Error ? error.message : "편집본 저장에 실패했습니다.");
    } finally {
      setMaterialBusy(false);
    }
  }

  async function handleLoadActivities() {
''',
)
replace_once(
    "desktop/src/App.tsx",
    '  const mode = isConnected ? connection.health.operation_mode : null;\n',
    '  const mode = isConnected ? connection.health.operation_mode : null;\n'
    '  const editingMaterial = editingMaterialId\n'
    '    ? materials.find((material) => material.id === editingMaterialId) ?? null\n'
    '    : null;\n',
)
replace_once(
    "desktop/src/App.tsx",
    '{material.status === "approved" && <button type="button" className="quiet-button" onClick={() => handlePrintMaterial(material)}>인쇄 / PDF</button>}',
    '{material.status !== "archived" && !materials.some((candidate) => candidate.parent_material_id === material.id) && <button type="button" className="quiet-button" disabled={materialBusy} onClick={() => setEditingMaterialId(material.id)}>직접 편집</button>}'
    '{material.status === "approved" && <button type="button" className="quiet-button" onClick={() => handlePrintMaterial(material)}>인쇄 / PDF</button>}',
)
replace_once(
    "desktop/src/App.tsx",
    '          {activeChild.stage === "infant_0_2" && (\n',
    '''          {editingMaterial && (
            <MaterialEditPanel
              key={editingMaterial.id}
              material={editingMaterial}
              busy={materialBusy}
              onSave={(title, contentMarkdown, note) =>
                handleParentEdit(editingMaterial.id, title, contentMarkdown, note)
              }
              onCancel={() => setEditingMaterialId(null)}
            />
          )}

          {activeChild.stage === "infant_0_2" && (
''',
)

rust_command = r'''
#[tauri::command]
async fn edit_material(
    material_id: String,
    title: String,
    content_markdown: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/edit"))
        .json(&serde_json::json!({
            "title": title,
            "content_markdown": content_markdown,
            "note": note,
        }))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "부모 편집본 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
'''
replace_once(
    "desktop/src-tauri/src/lib.rs",
    "#[tauri::command]\nasync fn get_growth_map(child_id: String) -> Result<GrowthMapDto, String> {\n",
    rust_command + "\n#[tauri::command]\nasync fn get_growth_map(child_id: String) -> Result<GrowthMapDto, String> {\n",
)
replace_once(
    "desktop/src-tauri/src/lib.rs",
    "            revise_material,\n            get_growth_map,\n",
    "            revise_material,\n            edit_material,\n            get_growth_map,\n",
)
