use serde::{Deserialize, Serialize};

use super::{client, ensure_success, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct MaterialResultRequest {
    outcome: String,
    observation: String,
    process: Option<String>,
    child_question: Option<String>,
    interest: Option<String>,
    difficulty_note: Option<String>,
    next_activity: Option<String>,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    activity_plan_id: Option<String>,
    #[serde(default)]
    photo_record_ids: Vec<String>,
}

#[tauri::command]
pub async fn record_material_result(
    material_id: String,
    request: MaterialResultRequest,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/results"
        ))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 결과 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn list_material_results(material_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/results"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 결과 이력 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
