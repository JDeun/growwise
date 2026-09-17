use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use super::{client, ensure_success, CORE_BASE_URL};

static OPERATION_COUNTER: AtomicU64 = AtomicU64::new(0);

fn next_operation_key(label: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let counter = OPERATION_COUNTER.fetch_add(1, Ordering::Relaxed);
    format!("desktop-{label}-{}-{nanos}-{counter}", std::process::id())
}

async fn post_idempotent_json(
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

#[derive(Debug, Serialize, Deserialize)]
pub struct BackgroundObservationRequest {
    child_id: String,
    observation: String,
    experience_axes: Vec<String>,
    activity_plan_id: Option<String>,
}

#[tauri::command]
pub async fn create_observation_background(
    request: BackgroundObservationRequest,
) -> Result<serde_json::Value, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/observations/background"),
        &body,
        "observation",
    )
    .await?;
    ensure_success(response, "관찰 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn generate_material_background(
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
        format!("{CORE_BASE_URL}/v1/children/{child_id}/materials/background"),
        &body,
        "material",
    )
    .await?;
    ensure_success(response, "학습 자료 기본 초안 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn revise_material_background(
    material_id: String,
    note: Option<String>,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/revise-background"
        ))
        .json(&serde_json::json!({"note": note}))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 수정본 기본 초안 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::next_operation_key;

    #[test]
    fn operation_keys_are_unique() {
        assert_ne!(next_operation_key("observation"), next_operation_key("observation"));
    }
}
