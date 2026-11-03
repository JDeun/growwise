use super::{client, ensure_success, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn get_conversation_evidence(
    child_id: String,
    source_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/children/{child_id}/evidence"))
        .query(&[("source_id", source_id)])
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
        .map_err(|_| "원본 근거를 확인하지 못했습니다. 다시 시도해 주세요.".to_string())?;
    ensure_success(
        response,
        "원본이 삭제되었거나 현재 아이에게 공유되지 않았습니다.",
    )
    .await?
    .json::<serde_json::Value>()
    .await
    .map_err(|_| "원본 근거 응답을 읽지 못했습니다.".to_string())
}
