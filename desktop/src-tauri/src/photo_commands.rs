use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use serde::{Deserialize, Serialize};

use super::{ensure_success, next_operation_key, CORE_CONNECTION};

const PHOTO_REQUEST_TIMEOUT: Duration = Duration::from_secs(90);

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct PhotoUploadInput {
    filename: String,
    mime_type: String,
    data_base64: String,
}

fn photo_client() -> Result<reqwest::Client, String> {
    let connection = CORE_CONNECTION
        .get()
        .ok_or_else(|| "GrowWise Core 연결 정보가 초기화되지 않았습니다.".to_string())?;
    let authorization = HeaderValue::from_str(&format!("Bearer {}", connection.session_token))
        .map_err(|error| format!("GrowWise Core 인증 헤더 생성 실패: {error}"))?;
    let mut headers = HeaderMap::new();
    headers.insert(AUTHORIZATION, authorization);
    reqwest::Client::builder()
        .default_headers(headers)
        .timeout(PHOTO_REQUEST_TIMEOUT)
        .build()
        .map_err(|error| error.to_string())
}

fn core_base_url() -> Result<String, String> {
    CORE_CONNECTION
        .get()
        .map(|connection| connection.base_url.clone())
        .ok_or_else(|| "GrowWise Core 연결 정보가 초기화되지 않았습니다.".to_string())
}

async fn post_photo_idempotent_json(
    url: String,
    body: &serde_json::Value,
    operation_label: &str,
) -> Result<reqwest::Response, String> {
    let key = next_operation_key(operation_label);
    let first = photo_client()?
        .post(&url)
        .header("Idempotency-Key", key.as_str())
        .json(body)
        .send()
        .await;

    match first {
        Ok(response) => Ok(response),
        Err(error) if error.is_timeout() || error.is_connect() => photo_client()?
            .post(&url)
            .header("Idempotency-Key", key.as_str())
            .json(body)
            .send()
            .await
            .map_err(|retry_error| retry_error.to_string()),
        Err(error) => Err(error.to_string()),
    }
}

#[tauri::command]
pub(crate) async fn create_photo_record(
    child_id: String,
    files: Vec<PhotoUploadInput>,
    user_context: Option<String>,
    manual_observation: Option<String>,
    ai_assist: bool,
    shared_child_ids: Vec<String>,
) -> Result<serde_json::Value, String> {
    let base_url = core_base_url()?;
    let body = serde_json::json!({
        "files": files,
        "user_context": user_context,
        "manual_observation": manual_observation,
        "ai_assist": ai_assist,
        "shared_child_ids": shared_child_ids,
    });
    let response = post_photo_idempotent_json(
        format!("{base_url}/v1/children/{child_id}/photo-records"),
        &body,
        "photo-record-create",
    )
    .await?;
    ensure_success(response, "사진 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn list_photo_records(child_id: String) -> Result<serde_json::Value, String> {
    let base_url = core_base_url()?;
    let response = photo_client()?
        .get(format!("{base_url}/v1/children/{child_id}/photo-records"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "사진 기록 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn commit_photo_record(
    record_id: String,
    observation: Option<String>,
) -> Result<serde_json::Value, String> {
    let base_url = core_base_url()?;
    let response = photo_client()?
        .post(format!("{base_url}/v1/photo-records/{record_id}/commit"))
        .json(&serde_json::json!({"observation": observation}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "사진 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn get_photo_asset(
    child_id: String,
    asset_id: String,
) -> Result<serde_json::Value, String> {
    let base_url = core_base_url()?;
    let response = photo_client()?
        .get(format!(
            "{base_url}/v1/children/{child_id}/photo-assets/{asset_id}"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "사진 원본 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
