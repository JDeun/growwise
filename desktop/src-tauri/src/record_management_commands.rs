use super::{client, ensure_success, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn retry_material_enhancement(
    material_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/retry-enhancement"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "자료 AI 보강 다시 시도 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn delete_conversation(session_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .delete(format!("{CORE_BASE_URL}/v1/conversations/{session_id}"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "대화 삭제 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn delete_entity_link(
    link_id: String,
    acting_child_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .delete(format!("{CORE_BASE_URL}/v1/links/{link_id}"))
        .query(&[("acting_child_id", acting_child_id)])
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "아이 연결 해제 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn retry_photo_record(record_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/photo-records/{record_id}/retry"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "사진 분석 다시 시도 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
