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
    llm_configured: bool,
    llm_reachable: bool,
    llm_features_enabled: bool,
    embedding_features_enabled: bool,
    model_provider: String,
}

#[derive(Debug, Serialize)]
struct CoreRuntimeStatus { started_by_desktop: bool }
#[derive(Debug, Serialize, Deserialize)]
struct ChildCreateInput { nickname: String, stage: String, age_months: Option<u16>, interests: Vec<String> }
#[derive(Debug, Serialize, Deserialize)]
struct ChildProfileDto { id: String, nickname: String, stage: String, age_months: Option<u16>, interests: Vec<String> }
#[derive(Debug, Serialize, Deserialize)]
struct ObservationCreateInput { child_id: String, observation: String, experience_axes: Vec<String>, activity_plan_id: Option<String> }
#[derive(Debug, Serialize, Deserialize)]
struct LearningLogDto { id: String, child_id: String, activity_plan_id: Option<String>, parent_observation: String, tags: Vec<String>, experience_axes: Vec<String>, interest: Option<String>, next_activity: Option<String>, created_at: Option<String> }
#[derive(Debug, Serialize, Deserialize)]
struct GrowthAxisDto { axis: String, state: String, observation_count: u32 }
#[derive(Debug, Serialize, Deserialize)]
struct GrowthMapDto { child_id: String, period_days: u32, total_logs_in_period: u32, tagged_logs_in_period: u32, axes: Vec<GrowthAxisDto> }
#[derive(Debug, Serialize, Deserialize)]
struct ActivitySuggestionDto { title: String, description: String, materials: Vec<String>, observation_cue: Option<String>, tags: Vec<String> }
#[derive(Debug, Serialize, Deserialize)]
struct InfantActivitySuggestionsDto { suggestions: Vec<ActivitySuggestionDto> }
#[derive(Debug, Serialize, Deserialize)]
struct ResourceCreateInput { kind: String, title: String, child_id: Option<String>, summary: Option<String>, content: Option<String>, source_url: Option<String>, source_name: Option<String>, author: Option<String>, tags: Vec<String>, stage_tags: Vec<String>, provenance: serde_json::Value }

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder().timeout(std::time::Duration::from_millis(8000)).build().map_err(|error| error.to_string())
}

async fn ensure_success(response: reqwest::Response, label: &str) -> Result<reqwest::Response, String> {
    if response.status().is_success() { return Ok(response); }
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    Err(format!("{label} ({status}): {body}"))
}

#[tauri::command]
async fn core_health() -> Result<CoreHealth, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/health")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "GrowWise Core health check failed").await?.json::<CoreHealth>().await.map_err(|error| error.to_string())
}
#[tauri::command]
fn core_runtime_status(manager: tauri::State<'_, CoreProcessManager>) -> CoreRuntimeStatus { CoreRuntimeStatus { started_by_desktop: manager.started_by_desktop() } }
#[tauri::command]
async fn create_child(request: ChildCreateInput) -> Result<ChildProfileDto, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/children")).json(&request).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "아이 프로필 저장 실패").await?.json::<ChildProfileDto>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_children() -> Result<Vec<ChildProfileDto>, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "아이 목록 조회 실패").await?.json::<Vec<ChildProfileDto>>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_observation(request: ObservationCreateInput) -> Result<LearningLogDto, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/observations")).json(&request).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "관찰 기록 저장 실패").await?.json::<LearningLogDto>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_observations(child_id: String) -> Result<Vec<LearningLogDto>, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/observations")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "관찰 기록 조회 실패").await?.json::<Vec<LearningLogDto>>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_activity(child_id: String, title: String, source_refs: Vec<String>) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/children/{child_id}/activities"))
        .json(&serde_json::json!({"title": title, "source_refs": source_refs, "parent_note": null}))
        .send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "활동 저장 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_activities(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/activities")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "활동 목록 조회 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn transition_activity(activity_id: String, status: String, parent_note: Option<String>) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/activities/{activity_id}/transition"))
        .json(&serde_json::json!({"status": status, "parent_note": parent_note}))
        .send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "활동 상태 변경 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_activity_observations(activity_id: String) -> Result<Vec<LearningLogDto>, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/activities/{activity_id}/observations")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "활동 관찰 기록 조회 실패").await?.json::<Vec<LearningLogDto>>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn search_child_context(child_id: String, query: String) -> Result<serde_json::Value, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/search")).query(&[("q", query.as_str()), ("limit", "20")]).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "자연어 검색 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_conversation(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/children/{child_id}/conversations")).json(&serde_json::json!({"title": null})).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "대화 세션 생성 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn append_conversation_turn(session_id: String, question: String) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/conversations/{session_id}/turns")).json(&serde_json::json!({"question": question, "limit": 8})).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "후속 질문 처리 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_resource(request: ResourceCreateInput) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/resources")).json(&request).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "자료 저장 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_resources(child_id: Option<String>) -> Result<serde_json::Value, String> {
    let mut request = client()?.get(format!("{CORE_BASE_URL}/v1/resources"));
    if let Some(id) = child_id.as_deref() { request = request.query(&[("child_id", id)]); }
    let response = request.send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "자료 목록 조회 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn generate_material(child_id: String, kind: String, topic: String, goal: Option<String>, source_refs: Vec<String>) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/children/{child_id}/materials"))
        .json(&serde_json::json!({"kind": kind, "topic": topic, "goal": goal, "source_refs": source_refs}))
        .send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "학습 자료 생성 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_materials(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/materials")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "생성 자료 목록 조회 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn review_material(material_id: String, status: String, note: Option<String>) -> Result<serde_json::Value, String> {
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/review")).json(&serde_json::json!({"status": status, "note": note})).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "자료 검토 상태 변경 실패").await?.json::<serde_json::Value>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn get_growth_map(child_id: String) -> Result<GrowthMapDto, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/growth-map?days=30")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "성장 맥락 조회 실패").await?.json::<GrowthMapDto>().await.map_err(|error| error.to_string())
}
#[tauri::command]
async fn get_infant_activities(child_id: String) -> Result<InfantActivitySuggestionsDto, String> {
    let response = client()?.get(format!("{CORE_BASE_URL}/v1/children/{child_id}/infant-activities?limit=3")).send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "영아 활동 추천 조회 실패").await?.json::<InfantActivitySuggestionsDto>().await.map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let resource_dir = app.path().resource_dir()?;
            let manager = CoreProcessManager::ensure_started(&resource_dir).map_err(std::io::Error::other)?;
            app.manage(manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_health, core_runtime_status, create_child, list_children, create_observation,
            list_observations, create_activity, list_activities, transition_activity,
            list_activity_observations, search_child_context, create_conversation,
            append_conversation_turn, create_resource, list_resources, generate_material,
            list_materials, review_material, get_growth_map, get_infant_activities
        ])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}