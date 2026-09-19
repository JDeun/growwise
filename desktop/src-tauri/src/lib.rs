mod background_write_commands;
mod backup_commands;
mod child_commands;
mod core_process;
mod discovery_commands;
mod learning_record_commands;
mod link_commands;
mod material_result_commands;
mod photo_commands;
mod study_commands;

use std::fmt;
use std::fs;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use background_write_commands::{
    create_observation_background, generate_material_background, revise_material_background,
};
use backup_commands::{create_backup, export_backup, import_backup, list_backups, restore_backup};
use child_commands::{
    create_child, delete_child, delete_child_avatar, list_children, set_child_avatar, update_child,
};
use core_process::CoreProcessManager;
use discovery_commands::{discover_education_resources, save_discovered_resource};
use learning_record_commands::{create_learning_record, list_learning_records};
use link_commands::{get_entity_backlinks, share_entity_with_child};
use material_result_commands::{list_material_results, record_material_result};
use photo_commands::{
    commit_photo_record, create_photo_record, get_photo_asset, list_photo_records,
};
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use serde::{Deserialize, Serialize};
use study_commands::{
    create_study_plan, get_study_weak_map, list_self_explanations, list_study_mistakes,
    list_study_plans, list_study_progress, list_study_reflections, recommend_study_resources,
    record_self_explanation, record_study_mistake, record_study_progress, record_study_reflection,
    update_study_plan_item_status,
};
use tauri::Manager;

#[derive(Debug)]
struct CoreConnection {
    base_url: String,
    session_token: String,
}

static CORE_CONNECTION: OnceLock<CoreConnection> = OnceLock::new();
static OPERATION_COUNTER: AtomicU64 = AtomicU64::new(0);

struct CoreBaseUrl;
const CORE_BASE_URL: CoreBaseUrl = CoreBaseUrl;

impl fmt::Display for CoreBaseUrl {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let connection = CORE_CONNECTION.get().ok_or(fmt::Error)?;
        formatter.write_str(&connection.base_url)
    }
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
struct CoreHealth {
    status: String,
    operation_mode: String,
    core_requires_llm: bool,
    llm_configured: bool,
    llm_reachable: bool,
    llm_model_id: Option<String>,
    llm_model_available: Option<bool>,
    llm_base_url: Option<String>,
    llm_features_enabled: bool,
    embedding_reachable: Option<bool>,
    embedding_model_id: Option<String>,
    embedding_model_available: Option<bool>,
    embedding_base_url: Option<String>,
    embedding_features_enabled: bool,
    vision_reachable: Option<bool>,
    vision_model_id: Option<String>,
    vision_model_available: Option<bool>,
    vision_base_url: Option<String>,
    vision_features_enabled: Option<bool>,
    model_provider: String,
}

#[derive(Debug, Serialize)]
struct CoreRuntimeStatus {
    started_by_desktop: bool,
}
#[derive(Debug, Serialize, Deserialize)]
struct ObservationCreateInput {
    child_id: String,
    observation: String,
    experience_axes: Vec<String>,
    activity_plan_id: Option<String>,
}
#[derive(Debug, Serialize, Deserialize)]
struct LearningLogDto {
    id: String,
    child_id: String,
    activity_plan_id: Option<String>,
    parent_observation: String,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    interest: Option<String>,
    next_activity: Option<String>,
    created_at: Option<String>,
}
#[derive(Debug, Serialize, Deserialize)]
struct GrowthAxisDto {
    axis: String,
    state: String,
    observation_count: u32,
}
#[derive(Debug, Serialize, Deserialize)]
struct GrowthLayerDto {
    key: String,
    label: String,
    axes: Vec<GrowthAxisDto>,
}
#[derive(Debug, Serialize, Deserialize)]
struct CoverageDiversityDto {
    state: String,
    observed_axis_count: u32,
    focus_axes: Vec<String>,
    note: String,
}
#[derive(Debug, Serialize, Deserialize)]
struct GrowthMapDto {
    child_id: String,
    period_days: u32,
    stage: Option<String>,
    total_logs_in_period: u32,
    tagged_logs_in_period: u32,
    axes: Vec<GrowthAxisDto>,
    layers: Vec<GrowthLayerDto>,
    diversity: CoverageDiversityDto,
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
#[derive(Debug, Serialize, Deserialize)]
struct ResourceCreateInput {
    kind: String,
    title: String,
    child_id: Option<String>,
    summary: Option<String>,
    content: Option<String>,
    source_url: Option<String>,
    source_name: Option<String>,
    author: Option<String>,
    tags: Vec<String>,
    stage_tags: Vec<String>,
    provenance: serde_json::Value,
}

fn client() -> Result<reqwest::Client, String> {
    let connection = CORE_CONNECTION
        .get()
        .ok_or_else(|| "GrowWise Core 연결 정보가 초기화되지 않았습니다.".to_string())?;
    let authorization = HeaderValue::from_str(&format!("Bearer {}", connection.session_token))
        .map_err(|error| format!("GrowWise Core 인증 헤더 생성 실패: {error}"))?;
    let mut headers = HeaderMap::new();
    headers.insert(AUTHORIZATION, authorization);
    reqwest::Client::builder()
        .default_headers(headers)
        .timeout(std::time::Duration::from_millis(8000))
        .build()
        .map_err(|error| error.to_string())
}

fn next_operation_key(label: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let counter = OPERATION_COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("desktop-{label}-{}-{nanos}-{counter}", std::process::id())
}

pub(crate) async fn post_idempotent_json(
    url: String,
    body: &serde_json::Value,
    operation_label: &str,
) -> Result<reqwest::Response, String> {
    let key = next_operation_key(operation_label);
    let first = client()?
        .post(&url)
        .header("Idempotency-Key", key.as_str())
        .json(body)
        .send()
        .await;

    match first {
        Ok(response) => Ok(response),
        Err(error) if error.is_timeout() || error.is_connect() => client()?
            .post(&url)
            .header("Idempotency-Key", key.as_str())
            .json(body)
            .send()
            .await
            .map_err(|retry_error| retry_error.to_string()),
        Err(error) => Err(error.to_string()),
    }
}

async fn ensure_success(
    response: reqwest::Response,
    label: &str,
) -> Result<reqwest::Response, String> {
    if response.status().is_success() {
        return Ok(response);
    }
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    let bounded_body: String = body.chars().take(4096).collect();
    Err(format!("{label} ({status}): {bounded_body}"))
}

#[tauri::command]
async fn core_health() -> Result<CoreHealth, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/health"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "GrowWise Core health check failed")
        .await?
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

fn is_loopback_url(url: &reqwest::Url) -> bool {
    if !matches!(url.scheme(), "http" | "https") {
        return false;
    }
    match url.host_str().map(|host| host.trim_matches(['[', ']']).to_ascii_lowercase()) {
        Some(host) if host == "localhost" || host.ends_with(".localhost") => true,
        Some(host) => host
            .parse::<std::net::IpAddr>()
            .map(|address| address.is_loopback())
            .unwrap_or(false),
        None => false,
    }
}

async fn pull_ollama_model(base_url: &str, model_id: &str) -> Result<(), String> {
    let endpoint = reqwest::Url::parse(&format!("{}/api/pull", base_url.trim_end_matches('/')))
        .map_err(|error| format!("로컬 AI 주소가 올바르지 않습니다: {error}"))?;
    if !is_loopback_url(&endpoint) {
        return Err("GrowWise는 자동 모델 준비를 로컬 Ollama에서만 허용합니다.".to_string());
    }

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(60 * 60))
        .build()
        .map_err(|error| error.to_string())?;
    let response = client
        .post(endpoint)
        .json(&serde_json::json!({"model": model_id, "stream": false}))
        .send()
        .await
        .map_err(|error| format!("AI 모델 준비 요청에 실패했습니다: {error}"))?;

    if response.status().is_success() {
        Ok(())
    } else {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        let bounded: String = body.chars().take(1024).collect();
        Err(format!("AI 모델 준비에 실패했습니다 ({status}): {bounded}"))
    }
}

#[tauri::command]
async fn prepare_local_ai(component: String) -> Result<String, String> {
    let health = core_health().await?;
    if health.model_provider.casefold() != "ollama" {
        return Err("자동 준비는 로컬 Ollama 구성에서만 사용할 수 있습니다.".to_string());
    }

    let mut targets: Vec<(String, String)> = Vec::new();
    match component.as_str() {
        "basic" => {
            if health.llm_model_available != Some(true) {
                if let (Some(base_url), Some(model_id)) =
                    (health.llm_base_url.clone(), health.llm_model_id.clone())
                {
                    targets.push((base_url, model_id));
                }
            }
            if health.embedding_model_available != Some(true) {
                if let (Some(base_url), Some(model_id)) = (
                    health.embedding_base_url.clone(),
                    health.embedding_model_id.clone(),
                ) {
                    targets.push((base_url, model_id));
                }
            }
        }
        "vision" => {
            if health.vision_model_available != Some(true) {
                if let (Some(base_url), Some(model_id)) =
                    (health.vision_base_url.clone(), health.vision_model_id.clone())
                {
                    targets.push((base_url, model_id));
                }
            }
        }
        _ => return Err("지원하지 않는 AI 준비 항목입니다.".to_string()),
    }

    if targets.is_empty() {
        return Ok("already_ready".to_string());
    }

    for (base_url, model_id) in targets {
        pull_ollama_model(&base_url, &model_id).await?;
    }
    Ok("prepared".to_string())
}
#[tauri::command]
async fn create_observation(request: ObservationCreateInput) -> Result<LearningLogDto, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/observations"),
        &body,
        "observation-sync",
    )
    .await?;
    ensure_success(response, "관찰 기록 저장 실패")
        .await?
        .json::<LearningLogDto>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_observations(child_id: String) -> Result<Vec<LearningLogDto>, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/observations"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "관찰 기록 조회 실패")
        .await?
        .json::<Vec<LearningLogDto>>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_activity(
    child_id: String,
    title: String,
    source_refs: Vec<String>,
) -> Result<serde_json::Value, String> {
    let body = serde_json::json!({
        "title": title,
        "source_refs": source_refs,
        "parent_note": null,
    });
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/activities"),
        &body,
        "activity",
    )
    .await?;
    ensure_success(response, "활동 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_activities(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children/{child_id}/activities"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn transition_activity(
    activity_id: String,
    status: String,
    parent_note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/activities/{activity_id}/transition"
        ))
        .json(&serde_json::json!({"status": status, "parent_note": parent_note}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 상태 변경 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_activity_observations(activity_id: String) -> Result<Vec<LearningLogDto>, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/activities/{activity_id}/observations"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 관찰 기록 조회 실패")
        .await?
        .json::<Vec<LearningLogDto>>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn search_child_context(
    child_id: String,
    query: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children/{child_id}/search"))
        .query(&[("q", query.as_str()), ("limit", "20")])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자연어 검색 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_conversation(child_id: String) -> Result<serde_json::Value, String> {
    let body = serde_json::json!({"title": null});
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/conversations"),
        &body,
        "conversation-create",
    )
    .await?;
    ensure_success(response, "대화 세션 생성 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_conversations(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/conversations"
        ))
        .query(&[("limit", "50")])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "대화 기록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn append_conversation_turn(
    session_id: String,
    question: String,
) -> Result<serde_json::Value, String> {
    let body = serde_json::json!({"question": question, "limit": 8});
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/conversations/{session_id}/turns"),
        &body,
        "conversation-turn",
    )
    .await?;
    ensure_success(response, "후속 질문 처리 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_resource(request: ResourceCreateInput) -> Result<serde_json::Value, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response =
        post_idempotent_json(format!("{CORE_BASE_URL}/v1/resources"), &body, "resource").await?;
    ensure_success(response, "자료 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_resources(child_id: Option<String>) -> Result<serde_json::Value, String> {
    let mut request = client()?.get(format!("{CORE_BASE_URL}/v1/resources"));
    if let Some(id) = child_id.as_deref() {
        request = request.query(&[("child_id", id)]);
    }
    let response = request.send().await.map_err(|error| error.to_string())?;
    ensure_success(response, "자료 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn update_resource(
    resource_id: String,
    request: ResourceCreateInput,
    acting_child_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .put(format!("{CORE_BASE_URL}/v1/resources/{resource_id}"))
        .query(&[("acting_child_id", acting_child_id.as_str())])
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 수정 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn delete_resource(
    resource_id: String,
    acting_child_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .delete(format!("{CORE_BASE_URL}/v1/resources/{resource_id}"))
        .query(&[("acting_child_id", acting_child_id.as_str())])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 삭제 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn generate_material(
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
        format!("{CORE_BASE_URL}/v1/children/{child_id}/materials"),
        &body,
        "material-generate",
    )
    .await?;
    ensure_success(response, "학습 자료 생성 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn list_materials(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children/{child_id}/materials"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "생성 자료 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn review_material(
    material_id: String,
    status: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/review"))
        .json(&serde_json::json!({"status": status, "note": note}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 검토 상태 변경 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn use_material(material_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/use"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 사용 준비 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn revise_material(
    material_id: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/revise"))
        .json(&serde_json::json!({"note": note}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 수정본 생성 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn edit_material(
    material_id: String,
    title: String,
    content_markdown: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/edit"))
        .json(&serde_json::json!({
            "title": title,
            "content_markdown": content_markdown,
            "note": note,
        }))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "부모 편집본 저장 실패")
        .await?
        .json::<serde_json::Value>()
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
    ensure_success(response, "성장 맥락 조회 실패")
        .await?
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
    ensure_success(response, "영아 활동 추천 조회 실패")
        .await?
        .json::<InfantActivitySuggestionsDto>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn get_infant_observation_hints(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/infant-observation-hints"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "영아 관찰 힌트 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn get_board_book_recommendations(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/board-books?limit=3"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "보드북 추천 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let resource_dir = app.path().resource_dir()?;
            let data_dir = app.path().app_data_dir()?;
            fs::create_dir_all(&data_dir)?;
            let manager = CoreProcessManager::ensure_started(&resource_dir, &data_dir)
                .map_err(std::io::Error::other)?;
            CORE_CONNECTION
                .set(CoreConnection {
                    base_url: manager.base_url().to_string(),
                    session_token: manager.session_token().to_string(),
                })
                .map_err(|_| {
                    std::io::Error::other("GrowWise Core 연결이 중복 초기화되었습니다.")
                })?;
            app.manage(manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_health,
            core_runtime_status,
            prepare_local_ai,
            create_child,
            update_child,
            set_child_avatar,
            delete_child_avatar,
            list_children,
            delete_child,
            create_observation,
            create_observation_background,
            list_observations,
            create_learning_record,
            list_learning_records,
            record_study_progress,
            list_study_progress,
            record_study_mistake,
            list_study_mistakes,
            record_study_reflection,
            list_study_reflections,
            record_self_explanation,
            list_self_explanations,
            get_study_weak_map,
            recommend_study_resources,
            create_study_plan,
            list_study_plans,
            update_study_plan_item_status,
            create_activity,
            list_activities,
            transition_activity,
            list_activity_observations,
            search_child_context,
            create_conversation,
            list_conversations,
            append_conversation_turn,
            create_resource,
            list_resources,
            update_resource,
            delete_resource,
            generate_material,
            generate_material_background,
            list_materials,
            review_material,
            use_material,
            revise_material,
            revise_material_background,
            edit_material,
            record_material_result,
            list_material_results,
            get_growth_map,
            get_infant_activities,
            get_infant_observation_hints,
            get_board_book_recommendations,
            create_photo_record,
            list_photo_records,
            commit_photo_record,
            get_photo_asset,
            discover_education_resources,
            save_discovered_resource,
            share_entity_with_child,
            get_entity_backlinks,
            list_backups,
            create_backup,
            restore_backup,
            export_backup,
            import_backup
        ])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}

#[cfg(test)]
mod tests {
    use super::next_operation_key;

    #[test]
    fn operation_keys_are_unique() {
        assert_ne!(
            next_operation_key("activity"),
            next_operation_key("activity")
        );
    }
}
