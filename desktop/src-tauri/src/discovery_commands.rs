use std::time::Duration;

use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};

use super::{ensure_success, CORE_CONNECTION};

const DISCOVERY_REQUEST_TIMEOUT: Duration = Duration::from_secs(35);

fn discovery_client() -> Result<reqwest::Client, String> {
    let connection = CORE_CONNECTION
        .get()
        .ok_or_else(|| "GrowWise Core 연결 정보가 초기화되지 않았습니다.".to_string())?;
    let authorization = HeaderValue::from_str(&format!("Bearer {}", connection.session_token))
        .map_err(|error| format!("GrowWise Core 인증 헤더 생성 실패: {error}"))?;
    let mut headers = HeaderMap::new();
    headers.insert(AUTHORIZATION, authorization);
    reqwest::Client::builder()
        .default_headers(headers)
        .timeout(DISCOVERY_REQUEST_TIMEOUT)
        .build()
        .map_err(|error| error.to_string())
}

fn core_base_url() -> Result<String, String> {
    CORE_CONNECTION
        .get()
        .map(|connection| connection.base_url.clone())
        .ok_or_else(|| "GrowWise Core 연결 정보가 초기화되지 않았습니다.".to_string())
}

#[tauri::command]
pub(crate) async fn discover_education_resources(
    child_id: String,
    query: Option<String>,
    latitude: Option<f64>,
    longitude: Option<f64>,
) -> Result<serde_json::Value, String> {
    if latitude.is_some() != longitude.is_some() {
        return Err("탐방 위치의 위도와 경도는 함께 입력해 주세요.".to_string());
    }
    let base_url = core_base_url()?;
    let mut request =
        discovery_client()?.get(format!("{base_url}/v1/children/{child_id}/discover"));
    if let Some(value) = query.as_deref().filter(|value| !value.trim().is_empty()) {
        request = request.query(&[("query", value)]);
    }
    if let (Some(latitude), Some(longitude)) = (latitude, longitude) {
        request = request.query(&[("latitude", latitude), ("longitude", longitude)]);
    }
    let response = request.send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "교육 자료 발견 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn save_discovered_resource(
    child_id: String,
    suggestion: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let base_url = core_base_url()?;
    let response = discovery_client()?
        .post(format!("{base_url}/v1/children/{child_id}/discover/save"))
        .json(&suggestion)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "발견 자료 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
