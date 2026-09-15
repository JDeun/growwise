from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "desktop/src/App.tsx",
    'import { MaterialEditPanel } from "./MaterialEditPanel";\n',
    'import { MaterialEditPanel } from "./MaterialEditPanel";\n'
    'import { StudyPanel } from "./StudyPanel";\n',
)
replace_once(
    "desktop/src/App.tsx",
    "        {activeChild && <>\n",
    "        {activeChild && <>\n"
    '          {(activeChild.stage === "middle" || activeChild.stage === "high") && '
    "<StudyPanel child={activeChild} />}\n",
)

rust_commands = r'''

async fn core_get_json(path: &str, label: &str) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}{path}"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, label)
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

async fn core_post_json(
    path: &str,
    payload: &serde_json::Value,
    label: &str,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}{path}"))
        .json(payload)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, label)
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn record_study_progress(
    child_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    core_post_json(
        &format!("/v1/children/{child_id}/study/progress"),
        &request,
        "진도 기록 저장 실패",
    )
    .await
}

#[tauri::command]
async fn record_study_mistake(
    child_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    core_post_json(
        &format!("/v1/children/{child_id}/study/mistakes"),
        &request,
        "실수 기록 저장 실패",
    )
    .await
}

#[tauri::command]
async fn record_study_reflection(
    child_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    core_post_json(
        &format!("/v1/children/{child_id}/study/reflections"),
        &request,
        "학습 회고 저장 실패",
    )
    .await
}

#[tauri::command]
async fn record_self_explanation(
    child_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    core_post_json(
        &format!("/v1/children/{child_id}/study/self-explanations"),
        &request,
        "자기설명 저장 실패",
    )
    .await
}

#[tauri::command]
async fn get_study_weak_map(child_id: String) -> Result<serde_json::Value, String> {
    core_get_json(
        &format!("/v1/children/{child_id}/study/weak-map"),
        "약점 지도 조회 실패",
    )
    .await
}

#[tauri::command]
async fn get_study_resources(
    child_id: String,
    subject: String,
    unit: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children/{child_id}/study/resources"))
        .query(&[
            ("subject", subject.as_str()),
            ("unit", unit.as_str()),
            ("limit", "5"),
        ])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "학습 연결 자료 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn create_study_plan(
    child_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    core_post_json(
        &format!("/v1/children/{child_id}/study/plans"),
        &request,
        "학습 계획 생성 실패",
    )
    .await
}

#[tauri::command]
async fn list_study_plans(child_id: String) -> Result<serde_json::Value, String> {
    core_get_json(
        &format!("/v1/children/{child_id}/study/plans"),
        "학습 계획 조회 실패",
    )
    .await
}
'''

replace_once(
    "desktop/src-tauri/src/lib.rs",
    "\n#[cfg_attr(mobile, tauri::mobile_entry_point)]\npub fn run() {\n",
    rust_commands + "\n#[cfg_attr(mobile, tauri::mobile_entry_point)]\npub fn run() {\n",
)
replace_once(
    "desktop/src-tauri/src/lib.rs",
    "            restore_backup,\n            export_backup,\n            import_backup\n",
    "            restore_backup,\n"
    "            export_backup,\n"
    "            import_backup,\n"
    "            record_study_progress,\n"
    "            record_study_mistake,\n"
    "            record_study_reflection,\n"
    "            record_self_explanation,\n"
    "            get_study_weak_map,\n"
    "            get_study_resources,\n"
    "            create_study_plan,\n"
    "            list_study_plans\n",
)
