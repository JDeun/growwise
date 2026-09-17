use serde::{Deserialize, Serialize};

use super::{client, ensure_success, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
pub struct LearningRecordRequest {
    kind: String,
    title: String,
    occurred_at: Option<String>,
    subject: Option<String>,
    institution: Option<String>,
    summary: String,
    learner_work: Option<String>,
    process: Option<String>,
    interest: Option<String>,
    difficulty_note: Option<String>,
    next_activity: Option<String>,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    shared_child_ids: Vec<String>,
}

#[tauri::command]
pub async fn create_learning_record(
    child_id: String,
    request: LearningRecordRequest,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/learning-records"
        ))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "학습 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn list_learning_records(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/learning-records"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "학습 기록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
