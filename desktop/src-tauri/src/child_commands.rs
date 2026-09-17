use serde::{Deserialize, Serialize};

use super::{client, ensure_success, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct ChildCreateInput {
    nickname: String,
    stage: String,
    age_months: Option<u16>,
    interests: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct ChildUpdateInput {
    nickname: String,
    stage: String,
    age_months: Option<u16>,
    interests: Vec<String>,
    primary_language: String,
    additional_languages: Vec<String>,
    learning_goals: Vec<String>,
    notes: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct ChildProfileDto {
    id: String,
    nickname: String,
    stage: String,
    age_months: Option<u16>,
    interests: Vec<String>,
    #[serde(default)]
    primary_language: String,
    #[serde(default)]
    additional_languages: Vec<String>,
    #[serde(default)]
    learning_goals: Vec<String>,
    #[serde(default)]
    notes: Option<String>,
}

#[tauri::command]
pub(crate) async fn create_child(request: ChildCreateInput) -> Result<ChildProfileDto, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/children"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "아이 프로필 저장 실패")
        .await?
        .json::<ChildProfileDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn update_child(
    child_id: String,
    request: ChildUpdateInput,
) -> Result<ChildProfileDto, String> {
    let response = client()?
        .put(format!("{CORE_BASE_URL}/v1/children/{child_id}"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "아이 프로필 수정 실패")
        .await?
        .json::<ChildProfileDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn list_children() -> Result<Vec<ChildProfileDto>, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "아이 목록 조회 실패")
        .await?
        .json::<Vec<ChildProfileDto>>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn delete_child(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .delete(format!("{CORE_BASE_URL}/v1/children/{child_id}"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "아이 데이터 영구 삭제 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
