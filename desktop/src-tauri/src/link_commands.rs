use serde_json::Value;

use super::{client, ensure_success, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn share_entity_with_child(
    source_id: String,
    child_id: String,
) -> Result<Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/links"))
        .json(&serde_json::json!({
            "source_id": source_id,
            "target_id": child_id,
            "relation": "child_scope",
            "label": null,
        }))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "문서 공유 링크 생성 실패")
        .await?
        .json::<Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn get_entity_backlinks(entity_id: String) -> Result<Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/links/{entity_id}"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "연결 문서 조회 실패")
        .await?
        .json::<Value>()
        .await
        .map_err(|error| error.to_string())
}
