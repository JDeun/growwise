mod core_process;

use std::fmt;
use std::fs;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};

use core_process::CoreProcessManager;
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

#[derive(Debug)]
struct CoreConnection {
    base_url: String,
    session_token: String,
}

static CORE_CONNECTION: OnceLock<CoreConnection> = OnceLock::new();

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

async fn ensure_success(
    response: reqwest::Response,
    label: &str,
) -> Result<reqwest::Response, String> {
    if response.status().is_success() {
        return Ok(response);
    }
    let status = response.status();
    let body = response.text().await.unwrap_or_default();
    Err(format!("{label} ({status}): {body}"))
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
#[tauri::command]
async fn create_child(request: ChildCreateInput) -> Result<ChildProfileDto, String> {
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
async fn list_children() -> Result<Vec<ChildProfileDto>, String> {
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
async fn create_observation(request: ObservationCreateInput) -> Result<LearningLogDto, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/observations"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
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
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/children/{child_id}/activities"))
        .json(&serde_json::json!({"title": title, "source_refs": source_refs, "parent_note": null}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
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
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/conversations"
        ))
        .json(&serde_json::json!({"title": null}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
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
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/conversations/{session_id}/turns"
        ))
        .json(&serde_json::json!({"question": question, "limit": 8}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "후속 질문 처리 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
#[tauri::command]
async fn create_resource(request: ResourceCreateInput) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/resources"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
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
) -> Result<serde_json::Value, String> {
    let response = client()?
        .put(format!("{CORE_BASE_URL}/v1/resources/{resource_id}"))
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
async fn delete_resource(resource_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .delete(format!("{CORE_BASE_URL}/v1/resources/{resource_id}"))
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
    let response = client()?.post(format!("{CORE_BASE_URL}/v1/children/{child_id}/materials"))
        .json(&serde_json::json!({"kind": kind, "topic": topic, "goal": goal, "source_refs": source_refs}))
        .send().await.map_err(|error| error.to_string())?;
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

#[tauri::command]
async fn list_backups() -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/admin/backups"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn create_backup() -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/admin/backups"))
        .json(&serde_json::json!({}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 생성 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn restore_backup(archive_name: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/admin/backups/{archive_name}/restore"
        ))
        .json(&serde_json::json!({"confirmed": true}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 복원 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

fn backup_path_from_list(
    backups: &serde_json::Value,
    archive_name: &str,
) -> Result<PathBuf, String> {
    let items = backups
        .as_array()
        .ok_or_else(|| "백업 목록 응답 형식이 올바르지 않습니다.".to_string())?;
    let item = items
        .iter()
        .find(|item| item.get("archive").and_then(serde_json::Value::as_str) == Some(archive_name))
        .ok_or_else(|| "내보낼 백업을 찾을 수 없습니다.".to_string())?;
    let path = item
        .get("path")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| "백업 경로가 없습니다.".to_string())?;
    let path = PathBuf::from(path);
    if !path.is_file() {
        return Err("백업 파일이 디스크에 없습니다.".to_string());
    }
    Ok(path)
}

fn json_string(value: &serde_json::Value, key: &str) -> Result<String, String> {
    value
        .get(key)
        .and_then(serde_json::Value::as_str)
        .map(ToOwned::to_owned)
        .ok_or_else(|| format!("백업 응답에 {key} 값이 없습니다."))
}

#[tauri::command]
async fn export_backup(
    app: tauri::AppHandle,
    archive_name: String,
) -> Result<Option<String>, String> {
    let backups = list_backups().await?;
    let source = backup_path_from_list(&backups, &archive_name)?;
    let selected = app
        .dialog()
        .file()
        .set_title("GrowWise 백업 내보내기")
        .set_file_name(&archive_name)
        .add_filter("GrowWise backup", &["zip"])
        .blocking_save_file();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let mut destination = selected
        .into_path()
        .map_err(|error| format!("선택한 저장 경로를 사용할 수 없습니다: {error}"))?;
    let has_zip_extension = destination
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("zip"))
        .unwrap_or(false);
    if !has_zip_extension {
        destination.set_extension("zip");
    }
    if source != destination {
        fs::copy(&source, &destination)
            .map_err(|error| format!("백업 파일 내보내기에 실패했습니다: {error}"))?;
    }
    Ok(Some(destination.display().to_string()))
}

#[tauri::command]
async fn import_backup(app: tauri::AppHandle) -> Result<Option<serde_json::Value>, String> {
    let selected = app
        .dialog()
        .file()
        .set_title("GrowWise 백업 가져오기")
        .add_filter("GrowWise backup", &["zip"])
        .blocking_pick_file();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let source = selected
        .into_path()
        .map_err(|error| format!("선택한 백업 경로를 사용할 수 없습니다: {error}"))?;
    if !source.is_file() {
        return Err("선택한 백업 파일을 찾을 수 없습니다.".to_string());
    }
    let is_zip = source
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("zip"))
        .unwrap_or(false);
    if !is_zip {
        return Err("GrowWise 백업은 .zip 파일이어야 합니다.".to_string());
    }

    // Always preserve the current state before attempting an external restore.
    let safety_backup = create_backup().await?;
    let safety_archive = json_string(&safety_backup, "archive")?;
    let safety_path = PathBuf::from(json_string(&safety_backup, "path")?);
    let backup_dir = safety_path
        .parent()
        .ok_or_else(|| "관리 백업 폴더를 확인할 수 없습니다.".to_string())?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("시스템 시간을 확인할 수 없습니다: {error}"))?
        .as_nanos();
    let imported_archive = format!("growwise-import-{stamp}.zip");
    let managed_copy = backup_dir.join(&imported_archive);
    fs::copy(&source, &managed_copy)
        .map_err(|error| format!("선택한 백업을 안전 영역으로 복사하지 못했습니다: {error}"))?;

    match restore_backup(imported_archive.clone()).await {
        Ok(mut result) => {
            if let Some(object) = result.as_object_mut() {
                object.insert(
                    "safety_backup".to_string(),
                    serde_json::Value::String(safety_archive),
                );
                object.insert(
                    "imported_archive".to_string(),
                    serde_json::Value::String(imported_archive),
                );
            }
            Ok(Some(result))
        }
        Err(error) => {
            let _ = fs::remove_file(&managed_copy);
            Err(format!(
                "외부 백업을 복원하지 못했습니다. 현재 상태 보호 백업({safety_archive})은 유지됩니다: {error}"
            ))
        }
    }
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
                .map_err(|_| std::io::Error::other("GrowWise Core 연결이 중복 초기화되었습니다."))?;
            app.manage(manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            core_health,
            core_runtime_status,
            create_child,
            list_children,
            create_observation,
            list_observations,
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
            list_materials,
            review_material,
            revise_material,
            edit_material,
            get_growth_map,
            get_infant_activities,
            get_infant_observation_hints,
            get_board_book_recommendations,
            list_backups,
            create_backup,
            restore_backup,
            export_backup,
            import_backup
        ])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}
