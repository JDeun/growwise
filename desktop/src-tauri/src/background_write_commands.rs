use serde::{Deserialize, Serialize};

use super::{client, ensure_success, post_idempotent_json, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
pub struct BackgroundObservationRequest {
    child_id: String,
    observation: String,
    experience_axes: Vec<String>,
    activity_plan_id: Option<String>,
}

#[tauri::command]
pub async fn create_observation_background(
    request: BackgroundObservationRequest,
) -> Result<serde_json::Value, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/observations/background"),
        &body,
        "observation",
    )
    .await?;
    ensure_success(response, "관찰 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn generate_material_background(
    child_id: String,
    kind: String,
    topic: String,
    goal: Option<String>,
    source_refs: Vec<String>,
) -> Result<serde_json::Value, String> {
    let body = serde_json::json!({
        "kind": kind,
        "topic": topic,
        "goal": goal,
        "source_refs": source_refs,
    });
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/materials/background"),
        &body,
        "material",
    )
    .await?;
    ensure_success(response, "학습 자료 기본 초안 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn revise_material_background(
    material_id: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/revise-background"
        ))
        .json(&serde_json::json!({"note": note}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 수정본 기본 초안 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
