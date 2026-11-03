use std::fs::{self, File};
use std::io::Write;
use std::path::Path;
use std::process::Command;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::Manager;

use super::core_process::CoreProcessManager;
use super::{core_health, is_loopback_url, CoreHealth};

const SETTINGS_FILE: &str = "local-model-settings.json";
const MAX_MODEL_RESPONSE: usize = 2 * 1024 * 1024;

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct LocalModelSettings {
    text: Option<String>,
    vision: Option<String>,
    embedding: Option<String>,
}

impl LocalModelSettings {
    pub(crate) fn select(&mut self, component: &str, model: &str) -> Result<(), String> {
        validate_model_name(model)?;
        let slot = match component {
            "text" => &mut self.text,
            "vision" => &mut self.vision,
            "embedding" => &mut self.embedding,
            _ => return Err("지원하지 않는 모델 용도입니다.".to_string()),
        };
        *slot = Some(model.to_string());
        Ok(())
    }
}

pub(crate) fn read_saved_model_settings(data_dir: &Path) -> Result<LocalModelSettings, String> {
    let file = data_dir.join(SETTINGS_FILE);
    let bytes = match fs::read(file) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(LocalModelSettings::default())
        }
        Err(error) => return Err(format!("모델 설정을 읽지 못했습니다: {error}")),
    };
    let settings: LocalModelSettings = serde_json::from_slice(&bytes).map_err(|error| {
        format!("모델 설정이 손상되었습니다. local-model-settings.json을 확인해 주세요: {error}")
    })?;
    for model in [&settings.text, &settings.vision, &settings.embedding]
        .into_iter()
        .flatten()
    {
        validate_model_name(model)?;
    }
    Ok(settings)
}

pub(crate) fn write_saved_model_settings(
    data_dir: &Path,
    settings: &LocalModelSettings,
) -> Result<(), String> {
    fs::create_dir_all(data_dir).map_err(|error| error.to_string())?;
    let temporary = data_dir.join(format!("{SETTINGS_FILE}.tmp"));
    let result = (|| -> Result<(), String> {
        let mut file = File::create(&temporary).map_err(|error| error.to_string())?;
        file.write_all(&serde_json::to_vec(settings).map_err(|error| error.to_string())?)
            .map_err(|error| error.to_string())?;
        file.sync_all().map_err(|error| error.to_string())?;
        fs::rename(&temporary, data_dir.join(SETTINGS_FILE)).map_err(|error| error.to_string())
    })();
    if result.is_err() {
        let _ = fs::remove_file(temporary);
    }
    result
}

pub(crate) fn apply_saved_model_settings(
    command: &mut Command,
    data_dir: &Path,
) -> Result<(), String> {
    let settings = read_saved_model_settings(data_dir)?;
    for (variable, provider, base_url, selection) in [
        (
            "GROWWISE_MODEL_ID",
            "GROWWISE_MODEL_PROVIDER",
            "GROWWISE_MODEL_BASE_URL",
            settings.text,
        ),
        (
            "GROWWISE_VISION_MODEL_ID",
            "GROWWISE_VISION_PROVIDER",
            "GROWWISE_VISION_BASE_URL",
            settings.vision,
        ),
        (
            "GROWWISE_EMBEDDING_MODEL_ID",
            "GROWWISE_EMBEDDING_PROVIDER",
            "GROWWISE_EMBEDDING_BASE_URL",
            settings.embedding,
        ),
    ] {
        if let Some(model) = selection {
            // A saved local choice must not rewrite a later remote/non-Ollama configuration.
            if command_setting(command, provider, "ollama").eq_ignore_ascii_case("ollama")
                && endpoint(
                    &command_setting(command, base_url, "http://127.0.0.1:11434"),
                    "tags",
                )
                .is_ok()
            {
                command.env(variable, model);
            }
        }
    }
    Ok(())
}

fn command_setting(command: &Command, variable: &str, default: &str) -> String {
    command
        .get_envs()
        .find(|(key, _)| *key == variable)
        .map(|(_, value)| {
            value
                .map(|value| value.to_string_lossy().into_owned())
                .unwrap_or_default()
        })
        .unwrap_or_else(|| std::env::var(variable).unwrap_or_else(|_| default.to_string()))
}

fn validate_model_name(model: &str) -> Result<(), String> {
    if model.is_empty()
        || model.len() > 512
        || !model.chars().all(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '.' | '-' | '_' | '/' | ':')
        })
        || !model
            .chars()
            .any(|character| character.is_ascii_alphanumeric())
    {
        return Err("설치된 모델의 올바른 이름을 선택해 주세요.".to_string());
    }
    Ok(())
}

fn endpoint(base_url: &str, operation: &str) -> Result<reqwest::Url, String> {
    let url = reqwest::Url::parse(&format!(
        "{}/api/{operation}",
        base_url.trim_end_matches('/')
    ))
    .map_err(|error| error.to_string())?;
    if !is_loopback_url(&url)
        || !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("모델 관리는 로컬 Ollama 주소에서만 사용할 수 있습니다.".to_string());
    }
    Ok(url)
}

fn configured_endpoint(health: &CoreHealth, component: &str) -> Result<String, String> {
    let base = match component {
        "text" if health.model_provider.eq_ignore_ascii_case("ollama") => &health.llm_base_url,
        "vision" => &health.vision_base_url,
        "embedding" => &health.embedding_base_url,
        _ => return Err("로컬 Ollama 모델 용도를 선택해 주세요.".to_string()),
    }
    .as_deref()
    .ok_or("이 용도에 로컬 Ollama가 설정되어 있지 않습니다.")?;
    endpoint(base, "tags")?;
    Ok(base.to_string())
}

fn model_client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .no_proxy()
        .timeout(Duration::from_secs(15))
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .map_err(|error| error.to_string())
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct InstalledLocalModel {
    name: String,
    size: u64,
    #[serde(default)]
    digest: String,
    modified_at: Option<String>,
}

#[derive(Deserialize)]
struct ModelList {
    models: Vec<InstalledLocalModel>,
}

async fn model_json<T: serde::de::DeserializeOwned>(
    mut response: reqwest::Response,
) -> Result<T, String> {
    if !response.status().is_success() {
        return Err(format!("로컬 모델 정보 요청 실패: {}", response.status()));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|error| error.to_string())? {
        if bytes.len() + chunk.len() > MAX_MODEL_RESPONSE {
            return Err("로컬 모델 정보 응답이 너무 큽니다.".to_string());
        }
        bytes.extend_from_slice(&chunk);
    }
    serde_json::from_slice(&bytes)
        .map_err(|error| format!("모델 정보 형식을 확인해 주세요: {error}"))
}

async fn installed_models(base_url: &str) -> Result<Vec<InstalledLocalModel>, String> {
    let response = model_client()?
        .get(endpoint(base_url, "tags")?)
        .send()
        .await
        .map_err(|error| format!("설치된 모델을 확인하지 못했습니다: {error}"))?;
    let result: ModelList = model_json(response).await?;
    for model in &result.models {
        validate_model_name(&model.name)?;
    }
    Ok(result.models)
}

fn check_capability(component: &str, capabilities: &[String]) -> Result<(), String> {
    let required = match component {
        "text" => "completion",
        "vision" => "vision",
        "embedding" => "embedding",
        _ => return Err("지원하지 않는 모델 용도입니다.".to_string()),
    };
    if capabilities.iter().any(|capability| capability == required) {
        Ok(())
    } else {
        Err(format!(
            "선택한 모델은 이 용도({required})를 지원하지 않습니다. 지원 모델을 선택해 주세요."
        ))
    }
}

async fn require_installed(base_url: &str, model: &str) -> Result<(), String> {
    validate_model_name(model)?;
    if installed_models(base_url)
        .await?
        .iter()
        .any(|installed| installed.name == model)
    {
        Ok(())
    } else {
        Err("설치된 목록에서 모델을 다시 선택해 주세요.".to_string())
    }
}

#[tauri::command]
pub(crate) async fn list_local_models(
    component: String,
) -> Result<Vec<InstalledLocalModel>, String> {
    let base = configured_endpoint(&core_health().await?, &component)?;
    installed_models(&base).await
}

#[tauri::command]
pub(crate) async fn remove_local_model(
    component: String,
    model: String,
    confirmed: bool,
) -> Result<(), String> {
    if !confirmed {
        return Err("모델 삭제 확인이 필요합니다.".to_string());
    }
    let base = configured_endpoint(&core_health().await?, &component)?;
    require_installed(&base, &model).await?;
    let response = model_client()?
        .delete(endpoint(&base, "delete")?)
        .json(&serde_json::json!({"model": model}))
        .send()
        .await
        .map_err(|error| format!("모델을 삭제하지 못했습니다: {error}"))?;
    if !response.status().is_success() {
        return Err(format!("로컬 모델 삭제 실패: {}", response.status()));
    }
    Ok(())
}

#[tauri::command]
pub(crate) async fn set_local_model(
    app: tauri::AppHandle,
    component: String,
    model: String,
) -> Result<(), String> {
    let base = configured_endpoint(&core_health().await?, &component)?;
    require_installed(&base, &model).await?;
    let response = model_client()?
        .post(endpoint(&base, "show")?)
        .json(&serde_json::json!({"model": model}))
        .send()
        .await
        .map_err(|error| format!("모델 지원 용도를 확인하지 못했습니다: {error}"))?;
    #[derive(Deserialize)]
    struct ModelInfo {
        capabilities: Vec<String>,
    }
    let info: ModelInfo = model_json(response).await?;
    check_capability(&component, &info.capabilities)?;
    tauri::async_runtime::spawn_blocking(move || {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| error.to_string())?;
        app.state::<CoreProcessManager>()
            .change_model_settings(&resource_dir, &component, &model)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn settings_survive_restart_and_only_override_selected_roles() {
        let root = std::env::temp_dir().join(format!(
            "growwise-model-settings-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let mut settings = LocalModelSettings::default();
        settings.select("text", "test-model:4b").unwrap();
        write_saved_model_settings(&root, &settings).unwrap();
        let mut command = Command::new("unused");
        command.env("GROWWISE_VISION_MODEL_ID", "kept:latest");
        apply_saved_model_settings(&mut command, &root).unwrap();
        let values: std::collections::HashMap<_, _> = command.get_envs().collect();
        assert_eq!(
            values[std::ffi::OsStr::new("GROWWISE_MODEL_ID")].unwrap(),
            "test-model:4b"
        );
        assert_eq!(
            values[std::ffi::OsStr::new("GROWWISE_VISION_MODEL_ID")].unwrap(),
            "kept:latest"
        );
        assert!(!values.contains_key(std::ffi::OsStr::new("GROWWISE_EMBEDDING_MODEL_ID")));
        let mut remote = Command::new("unused");
        remote.env("GROWWISE_MODEL_PROVIDER", "openai_compatible");
        remote.env("GROWWISE_MODEL_ID", "remote-selection");
        apply_saved_model_settings(&mut remote, &root).unwrap();
        assert_eq!(
            command_setting(&remote, "GROWWISE_MODEL_ID", ""),
            "remote-selection"
        );
        let mut remote_ollama = Command::new("unused");
        remote_ollama.env("GROWWISE_MODEL_PROVIDER", "ollama");
        remote_ollama.env("GROWWISE_MODEL_BASE_URL", "https://remote.invalid");
        remote_ollama.env("GROWWISE_MODEL_ID", "remote-ollama-selection");
        apply_saved_model_settings(&mut remote_ollama, &root).unwrap();
        assert_eq!(
            command_setting(&remote_ollama, "GROWWISE_MODEL_ID", ""),
            "remote-ollama-selection"
        );
        fs::write(root.join(SETTINGS_FILE), b"corrupt").unwrap();
        assert!(read_saved_model_settings(&root).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn model_management_rejects_remote_redirect_inputs_and_invalid_names() {
        for url in [
            "https://example.invalid",
            "http://127.0.0.1@private.invalid",
            "http://127.0.0.1?redirect=remote",
            "file:///tmp/models",
        ] {
            assert!(endpoint(url, "tags").is_err());
        }
        for url in [
            "http://127.0.0.1:11434",
            "http://localhost:11434",
            "http://[::1]:11434",
        ] {
            assert!(endpoint(url, "tags").is_ok());
        }
        for name in [
            "",
            "../../ ",
            "test\nmodel",
            "http://remote?key=secret",
            "::",
        ] {
            assert!(validate_model_name(name).is_err());
        }
        assert!(validate_model_name("library/test-model:latest").is_ok());
    }

    #[test]
    fn incompatible_model_roles_are_rejected_before_persisting() {
        let text_only = vec!["completion".to_string()];
        assert!(check_capability("text", &text_only).is_ok());
        assert!(check_capability("vision", &text_only).is_err());
        assert!(check_capability("embedding", &text_only).is_err());
        assert!(check_capability("embedding", &["embedding".to_string()]).is_ok());
        assert!(
            check_capability("vision", &["vision".to_string(), "completion".to_string()]).is_ok()
        );
        assert!(check_capability("text", &[]).is_err());
    }
}
