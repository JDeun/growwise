use serde::{Deserialize, Serialize};

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

#[tauri::command]
async fn core_health() -> Result<CoreHealth, String> {
    let response = reqwest::Client::new()
        .get("http://127.0.0.1:8765/health")
        .timeout(std::time::Duration::from_millis(2500))
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![core_health])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}
