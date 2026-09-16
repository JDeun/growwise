use serde_json::Value;

use super::{client, ensure_success, CORE_BASE_URL};

async fn post_value(url: String, body: &Value, label: &str) -> Result<Value, String> {
    let response = client()?
        .post(url)
        .json(body)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, label)
        .await?
        .json::<Value>()
        .await
        .map_err(|error| error.to_string())
}

async fn get_value(url: String, label: &str) -> Result<Value, String> {
    let response = client()?
        .get(url)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, label)
        .await?
        .json::<Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn record_study_progress(
    child_id: String,
    request: Value,
) -> Result<Value, String> {
    post_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/progress"),
        &request,
        "학습 진도 저장 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn list_study_progress(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/progress"),
        "학습 진도 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn record_study_mistake(
    child_id: String,
    request: Value,
) -> Result<Value, String> {
    post_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/mistakes"),
        &request,
        "오답 기록 저장 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn list_study_mistakes(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/mistakes"),
        "오답 기록 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn record_study_reflection(
    child_id: String,
    request: Value,
) -> Result<Value, String> {
    post_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/reflections"),
        &request,
        "학습 회고 저장 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn list_study_reflections(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/reflections"),
        "학습 회고 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn record_self_explanation(
    child_id: String,
    request: Value,
) -> Result<Value, String> {
    post_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/self-explanations"),
        &request,
        "자기설명 기록 저장 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn list_self_explanations(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/self-explanations"),
        "자기설명 기록 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn get_study_weak_map(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/weak-map?limit=12"),
        "복습 지도 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn recommend_study_resources(
    child_id: String,
    subject: String,
    unit: String,
) -> Result<Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/study/resources"
        ))
        .query(&[
            ("subject", subject.as_str()),
            ("unit", unit.as_str()),
            ("limit", "5"),
        ])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "학습 자료 추천 조회 실패")
        .await?
        .json::<Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn create_study_plan(child_id: String, request: Value) -> Result<Value, String> {
    post_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/plans"),
        &request,
        "학습 계획 생성 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn list_study_plans(child_id: String) -> Result<Value, String> {
    get_value(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/study/plans"),
        "학습 계획 조회 실패",
    )
    .await
}

#[tauri::command]
pub(crate) async fn update_study_plan_item_status(
    child_id: String,
    plan_id: String,
    item_index: usize,
    status: String,
) -> Result<Value, String> {
    post_value(
        format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/study/plans/{plan_id}/items/{item_index}/status"
        ),
        &serde_json::json!({"status": status}),
        "학습 계획 상태 변경 실패",
    )
    .await
}
