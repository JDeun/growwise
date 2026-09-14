mod core_process;

use core_process::CoreProcessManager;
use serde::{Deserialize, Serialize};
use tauri::Manager;

const CORE_BASE_URL: &str = "http://127.0.0.1:8765";

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
struct CoreHealth {
    status: String,
    operation_mode: String,
    core_requires_llm: bool,
    llm_features_enabled: bool,
    embedding_features_enabled: bool,
    model_provider: String,
}

#[derive(Debug, Serialize)]
struct CoreRuntimeStatus {
    started_by_desktop: bool,
}

#[derive(Debug, Serialize, Deserialize)]
struct ChildCreateInput {
    nickname: String,
    stage: String,
    age_months: Option<u16>,
    interests: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ChildProfileDto {
    id: String,
    nickname: String,
    stage: String,
    age_months: Option<u16>,
    interests: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ObservationCreateInput {
    child_id: String,
    observation: String,
    experience_axes: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct LearningLogDto {
    id: String,
    child_id: String,
    parent_observation: String,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    interest: Option<String>,
    next_activity: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct GrowthAxisDto {
    axis: String,
    state: String,
    observation_count: u32,
}

#[derive(Debug, Serialize, Deserialize)]
struct GrowthMapDto {
    child_id: String,
    period_days: u32,
    total_logs_in_period: u32,
    tagged_logs_in_period: u32,
    axes: Vec<GrowthAxisDto>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ActivitySuggestionDto {
    title: String,
    description: String,
    materials: Vec<String>,
    observation_cue: Option<String>,
    tags: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct InfantActivitySuggestionsDto {
    suggestions: Vec<ActivitySuggestionDto>,
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(std::time::Duration::from_millis(8000))
        .build()
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn core_health() -> Result<CoreHealth, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/health"))
        .send()
        .await
        .map_err(|error| error.to_string())?;

    if !response.status().is_success() {
        return Err(format!("GrowWise Core health check failed: {}", response.status()));
    }

    response
        .json::<CoreHealth>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn core_runtime_status(manager: tauri::State<'_, CoreProcessManager>) -> CoreRuntimeStatus {
    CoreRuntimeStatus {
        started_by_desktop: manager.started_by_desktop(),
    }
}

#[tauri::command]
async fn create_child(request: ChildCreateInput) -> Result<ChildProfileDto, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/children"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("아이 프로필 저장 실패 ({status}): {body}"));
    }

    response
        .json::<ChildProfileDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn create_observation(request: ObservationCreateInput) -> Result<LearningLogDto, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/observations"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("관찰 기록 저장 실패 ({status}): {body}"));
    }

    response
        .json::<LearningLogDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn get_growth_map(child_id: String) -> Result<GrowthMapDto, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/growth-map?days=30"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("성장 맥락 조회 실패 ({status}): {body}"));
    }

    response
        .json::<GrowthMapDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn get_infant_activities(child_id: String) -> Result<InfantActivitySuggestionsDto, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/infant-activities?limit=3"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(format!("영아 활동 추천 조회 실패 ({status}): {body}"));
    }

    response
        .json::<InfantActivitySuggestionsDto>()
        .await
        .map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let resource_dir = app.path().resource_dir()?;
            let manager =
                CoreProcessManager::ensure_started(&resource_dir).map_err(std::io::Error::other)?;
            app.manage(manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_health,
            core_runtime_status,
            create_child,
            create_observation,
            get_growth_map,
            get_infant_activities
        ])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}
