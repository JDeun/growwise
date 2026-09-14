mod core_process;

use core_process::CoreProcessManager;
use serde::{Deserialize, Serialize};
use tauri::Manager;

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

#[derive(Debug, Serialize)]
struct CoreRuntimeStatus {
    started_by_desktop: bool,
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

#[tauri::command]
fn core_runtime_status(manager: tauri::State<'_, CoreProcessManager>) -> CoreRuntimeStatus {
    CoreRuntimeStatus {
        started_by_desktop: manager.started_by_desktop(),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let manager = CoreProcessManager::ensure_started().map_err(std::io::Error::other)?;
            app.manage(manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![core_health, core_runtime_status])
        .run(tauri::generate_context!())
        .expect("error while running GrowWise desktop application");
}
