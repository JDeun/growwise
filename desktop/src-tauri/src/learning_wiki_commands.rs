use super::{client, ensure_success, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn get_learning_wiki(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/learning-wiki"
        ))
        .timeout(std::time::Duration::from_secs(400))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "성장 맥락 불러오기 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn rebuild_learning_wiki(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/learning-wiki/rebuild"
        ))
        .timeout(std::time::Duration::from_secs(400))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "성장 맥락 다시 정리 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
