use super::{ensure_success, client, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn record_material_result(
    material_id: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/materials/{material_id}/results"))
        .json(&request)
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 결과 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn list_material_results(
    material_id: String,
) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/materials/{material_id}/results"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 결과 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}
