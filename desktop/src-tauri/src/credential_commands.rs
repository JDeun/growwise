use std::process::Command;

use serde::{Deserialize, Serialize};
use tauri::Manager;

use super::core_process::CoreProcessManager;
use super::{client, CORE_BASE_URL};

#[cfg(any(target_os = "macos", target_os = "windows"))]
const KEYRING_SERVICE: &str = "io.github.jdeun.growwise";

#[cfg(all(test, any(target_os = "macos", target_os = "windows")))]
mod native_roundtrip {
    #[test]
    #[ignore = "uses a unique synthetic entry in the OS credential store"]
    fn native_store_roundtrip_without_touching_product_credentials() {
        let account = format!(
            "synthetic-{}-{:?}",
            std::process::id(),
            std::time::SystemTime::now()
        );
        let entry = keyring::Entry::new("io.github.jdeun.growwise.validation", &account).unwrap();
        assert!(matches!(entry.get_password(), Err(keyring::Error::NoEntry)));
        entry
            .set_password("synthetic-validation-only")
            .expect("synthetic key save");
        assert_eq!(
            entry.get_password().expect("synthetic key read"),
            "synthetic-validation-only"
        );
        entry.set_password("").expect("synthetic disable marker");
        assert_eq!(entry.get_password().expect("synthetic marker read"), "");
        entry.delete_credential().expect("synthetic key cleanup");
        assert!(matches!(entry.get_password(), Err(keyring::Error::NoEntry)));
    }
}

const SERVICES: [(&str, &str); 6] = [
    ("data4library", "GROWWISE_DATA4LIBRARY_API_KEY"),
    ("google_books", "GROWWISE_GOOGLE_BOOKS_API_KEY"),
    ("national_library", "GROWWISE_NATIONAL_LIBRARY_API_KEY"),
    ("krdict", "GROWWISE_KRDICT_API_KEY"),
    ("data_go_kr", "GROWWISE_DATA_GO_KR_SERVICE_KEY"),
    ("model", "GROWWISE_MODEL_API_KEY"),
];

fn environment_variable(service_id: &str) -> Result<&'static str, String> {
    SERVICES
        .iter()
        .find(|(id, _)| *id == service_id)
        .map(|(_, variable)| *variable)
        .ok_or_else(|| "지원하지 않는 API 서비스입니다.".to_string())
}

fn validate_secret(value: &str) -> Result<&str, String> {
    let value = value.trim();
    if value.is_empty()
        || value.len() > 8192
        || value
            .chars()
            .any(|character| character.is_control() || character.is_whitespace())
    {
        return Err("API 키는 공백·줄바꿈 없이 8,192자 이내로 입력해 주세요.".to_string());
    }
    Ok(value)
}

pub(crate) fn read_saved_credential(service_id: &str) -> Result<Option<String>, String> {
    environment_variable(service_id)?;
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    {
        let entry = keyring::Entry::new(KEYRING_SERVICE, service_id)
            .map_err(|_| "OS 보안 저장소를 열지 못했습니다.".to_string())?;
        match entry.get_password() {
            Ok(value) => Ok(Some(value)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(_) => Err(
                "OS 보안 저장소에 접근하지 못했습니다. 잠금과 접근 권한을 확인해 주세요."
                    .to_string(),
            ),
        }
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        Err("이 운영체제에서는 API 키 보안 저장을 지원하지 않습니다.".to_string())
    }
}

pub(crate) fn write_saved_credential(service_id: &str, value: Option<&str>) -> Result<(), String> {
    environment_variable(service_id)?;
    if let Some(value) = value.filter(|value| !value.is_empty()) {
        validate_secret(value)?;
    }
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    {
        let entry = keyring::Entry::new(KEYRING_SERVICE, service_id)
            .map_err(|_| "OS 보안 저장소를 열지 못했습니다.".to_string())?;
        match value {
            // An empty entry explicitly disables a previously inherited environment credential.
            Some(value) => entry
                .set_password(value)
                .map_err(|_| "API 키를 OS 보안 저장소에 저장하지 못했습니다.".to_string()),
            None => match entry.delete_credential() {
                Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
                Err(_) => Err("API 키의 이전 보안 저장 상태를 복원하지 못했습니다.".to_string()),
            },
        }
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        Err("이 운영체제에서는 API 키 보안 저장을 지원하지 않습니다.".to_string())
    }
}

#[cfg(any(target_os = "macos", target_os = "windows", test))]
fn apply_credentials(
    command: &mut Command,
    mut read: impl FnMut(&str) -> Result<Option<String>, String>,
) -> Result<(), String> {
    for (service_id, variable) in SERVICES {
        let result = read(service_id).and_then(|value| {
            if let Some(value) = value.as_deref().filter(|value| !value.is_empty()) {
                validate_secret(value)?;
            }
            Ok(value)
        });
        let saved = match result {
            Ok(value) => value,
            Err(_) => {
                // Optional API access must fail closed without blocking the family's local Core.
                for (_, variable) in SERVICES {
                    command.env_remove(variable);
                }
                return Ok(());
            }
        };
        if let Some(value) = saved {
            if value.is_empty() {
                command.env_remove(variable);
            } else {
                command.env(variable, value);
            }
        }
    }
    Ok(())
}

pub(crate) fn apply_saved_credentials(command: &mut Command) -> Result<(), String> {
    #[cfg(any(target_os = "macos", target_os = "windows"))]
    {
        apply_credentials(command, read_saved_credential)
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        let _ = command;
        Ok(())
    }
}

#[derive(Debug, Serialize)]
pub(crate) struct ApiCredentialStatus {
    service_id: &'static str,
    configured: bool,
    source: &'static str,
    supported: bool,
}

fn credential_status(
    service_id: &'static str,
    saved: Option<&str>,
    environment: bool,
    supported: bool,
) -> ApiCredentialStatus {
    let source = match saved {
        Some("") => "disabled",
        Some(_) => "saved",
        None if environment => "environment",
        None => "none",
    };
    ApiCredentialStatus {
        service_id,
        configured: matches!(source, "saved" | "environment"),
        source,
        supported,
    }
}

#[tauri::command]
pub(crate) async fn list_api_credentials() -> Result<Vec<ApiCredentialStatus>, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let supported = cfg!(any(target_os = "macos", target_os = "windows"));
        SERVICES
            .iter()
            .map(|(service_id, variable)| {
                let saved = if supported {
                    read_saved_credential(service_id)?
                } else {
                    None
                };
                let environment = std::env::var_os(variable).is_some_and(|value| !value.is_empty());
                Ok(credential_status(
                    service_id,
                    saved.as_deref(),
                    environment,
                    supported,
                ))
            })
            .collect()
    })
    .await
    .map_err(|_| "API 키 상태를 확인하지 못했습니다.".to_string())?
}

#[tauri::command]
pub(crate) async fn save_api_credential(
    app: tauri::AppHandle,
    service_id: String,
    value: String,
) -> Result<(), String> {
    environment_variable(&service_id)?;
    let value = validate_secret(&value)?.to_string();
    tauri::async_runtime::spawn_blocking(move || {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|_| "앱 경로를 확인하지 못했습니다.".to_string())?;
        app.state::<CoreProcessManager>().change_credential(
            &resource_dir,
            &service_id,
            Some(&value),
        )
    })
    .await
    .map_err(|_| "API 키 설정을 적용하지 못했습니다.".to_string())?
}

#[tauri::command]
pub(crate) async fn delete_api_credential(
    app: tauri::AppHandle,
    service_id: String,
) -> Result<(), String> {
    environment_variable(&service_id)?;
    tauri::async_runtime::spawn_blocking(move || {
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|_| "앱 경로를 확인하지 못했습니다.".to_string())?;
        app.state::<CoreProcessManager>()
            .change_credential(&resource_dir, &service_id, Some(""))
    })
    .await
    .map_err(|_| "API 키 해제를 적용하지 못했습니다.".to_string())?
}

#[derive(Deserialize, Serialize)]
pub(crate) struct ApiCredentialConnection {
    service: String,
    status: String,
    message: String,
}

#[tauri::command]
pub(crate) async fn test_api_credential(
    service_id: String,
) -> Result<ApiCredentialConnection, String> {
    environment_variable(&service_id)?;
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/admin/integrations/{service_id}/test"
        ))
        .timeout(std::time::Duration::from_secs(150))
        .send()
        .await
        .map_err(|_| "실제 API 연결 확인 요청을 완료하지 못했습니다.".to_string())?;
    if !response.status().is_success() {
        return Err("실제 API 연결 확인 요청이 실패했습니다.".to_string());
    }
    response
        .json()
        .await
        .map_err(|_| "API 연결 확인 응답을 읽지 못했습니다.".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::ffi::OsStr;

    #[test]
    fn only_allowlisted_service_ids_and_bounded_secrets_are_accepted() {
        assert_eq!(
            environment_variable("data4library").unwrap(),
            "GROWWISE_DATA4LIBRARY_API_KEY"
        );
        assert!(environment_variable("GROWWISE_SESSION_TOKEN").is_err());
        assert!(environment_variable("../model").is_err());
        assert_eq!(
            validate_secret("  synthetic-test-key  ").unwrap(),
            "synthetic-test-key"
        );
        assert!(validate_secret("").is_err());
        assert!(validate_secret("synthetic\nkey").is_err());
        assert!(validate_secret(&"x".repeat(8193)).is_err());
    }

    #[test]
    fn saved_keys_and_explicit_disables_reach_only_allowlisted_child_environment() {
        let mut command = Command::new("unused");
        command.env("GROWWISE_GOOGLE_BOOKS_API_KEY", "inherited-test-key");
        command.env("GROWWISE_SESSION_TOKEN", "unchanged-test-token");
        apply_credentials(&mut command, |service| {
            Ok(match service {
                "data4library" => Some("synthetic-test-key".to_string()),
                "google_books" => Some(String::new()),
                _ => None,
            })
        })
        .unwrap();
        let values: HashMap<_, _> = command.get_envs().collect();
        assert_eq!(
            values[OsStr::new("GROWWISE_DATA4LIBRARY_API_KEY")].unwrap(),
            "synthetic-test-key"
        );
        assert_eq!(values[OsStr::new("GROWWISE_GOOGLE_BOOKS_API_KEY")], None);
        assert_eq!(
            values[OsStr::new("GROWWISE_SESSION_TOKEN")].unwrap(),
            "unchanged-test-token"
        );
        assert!(!values.contains_key(OsStr::new("GROWWISE_MODEL_REMOTE_ALLOWED")));
    }

    #[test]
    fn status_serialization_never_returns_a_secret() {
        for (saved, environment, source, configured) in [
            (Some("synthetic-test-key"), false, "saved", true),
            (Some(""), true, "disabled", false),
            (None, true, "environment", true),
            (None, false, "none", false),
        ] {
            let status = credential_status("model", saved, environment, true);
            assert_eq!(status.source, source);
            assert_eq!(status.configured, configured);
            assert!(!serde_json::to_string(&status)
                .unwrap()
                .contains("synthetic-test-key"));
        }
    }

    #[test]
    fn unavailable_keychain_disables_only_credentials_without_blocking_core() {
        let mut command = Command::new("unused");
        command.env("GROWWISE_GOOGLE_BOOKS_API_KEY", "synthetic-inherited-key");
        command.env("GROWWISE_SESSION_TOKEN", "synthetic-session");
        apply_credentials(&mut command, |service| {
            if service == "google_books" {
                Err("locked test store".to_string())
            } else {
                Ok(Some("synthetic-test-key".to_string()))
            }
        })
        .unwrap();
        let values: HashMap<_, _> = command.get_envs().collect();
        for (_, variable) in SERVICES {
            assert_eq!(values[OsStr::new(variable)], None);
        }
        assert_eq!(
            values[OsStr::new("GROWWISE_SESSION_TOKEN")].unwrap(),
            "synthetic-session"
        );
    }
}
