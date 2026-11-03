//! Explicit, signed application updates. No endpoint or key is accepted from the WebView.

use std::sync::atomic::{AtomicBool, Ordering};
#[cfg(feature = "updater")]
use std::sync::Mutex;
#[cfg(feature = "updater")]
use std::time::Duration;

use serde::Serialize;
#[cfg(feature = "updater")]
use tauri::Manager;
use tauri::{AppHandle, State};
#[cfg(feature = "updater")]
use tauri_plugin_updater::{Update, UpdaterExt};

const NOT_CONFIGURED: &str = "이 설치본은 자동 업데이트가 설정되지 않았습니다.";
#[cfg(feature = "updater")]
const MAX_UPDATE_BYTES: usize = 512 * 1024 * 1024;

#[derive(Default)]
pub(crate) struct AppUpdater {
    busy: AtomicBool,
    checked: AtomicBool,
    #[cfg(feature = "updater")]
    pending: Mutex<Option<Update>>,
}

struct Operation<'a>(&'a AtomicBool);

impl Drop for Operation<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::Release);
    }
}

impl AppUpdater {
    fn begin(&self) -> Result<Operation<'_>, String> {
        self.busy
            .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|_| "업데이트 작업이 진행 중입니다.".to_string())?;
        Ok(Operation(&self.busy))
    }
}

#[derive(Serialize)]
pub(crate) struct AppUpdateStatus {
    configured: bool,
    current_version: String,
    checked: bool,
    available_version: Option<String>,
    notes: Option<String>,
}

fn safe_https_url(value: &str) -> bool {
    reqwest::Url::parse(value).is_ok_and(|url| {
        url.scheme() == "https"
            && url.host_str().is_some()
            && url.username().is_empty()
            && url.password().is_none()
            && url.fragment().is_none()
            && !value.chars().any(char::is_control)
    })
}

fn trusted_config(config: Option<&serde_json::Value>) -> bool {
    let Some(config) = config else { return false };
    config
        .get("pubkey")
        .and_then(|value| value.as_str())
        .is_some_and(|key| !key.trim().is_empty())
        && config
            .get("requireSignedVersion")
            .and_then(|value| value.as_bool())
            == Some(true)
        && [
            "dangerousInsecureTransportProtocol",
            "dangerousAcceptInvalidCerts",
            "dangerousAcceptInvalidHostnames",
            "allowDowngrades",
        ]
        .iter()
        .all(|key| config.get(key).and_then(|value| value.as_bool()) != Some(true))
        && config
            .get("endpoints")
            .and_then(|value| value.as_array())
            .is_some_and(|endpoints| {
                !endpoints.is_empty()
                    && endpoints
                        .iter()
                        .all(|value| value.as_str().is_some_and(safe_https_url))
            })
}

pub(crate) fn configured(app: &AppHandle) -> bool {
    cfg!(feature = "updater") && trusted_config(app.config().plugins.0.get("updater"))
}

pub(crate) fn register(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    #[cfg(feature = "updater")]
    if configured(app) {
        app.plugin(tauri_plugin_updater::Builder::new().build())?;
    }
    #[cfg(not(feature = "updater"))]
    let _ = app;
    Ok(())
}

fn status(app: &AppHandle, state: &AppUpdater) -> Result<AppUpdateStatus, String> {
    #[cfg(feature = "updater")]
    let pending = state
        .pending
        .lock()
        .map_err(|_| "업데이트 상태를 다시 확인해 주세요.")?;
    Ok(AppUpdateStatus {
        configured: configured(app),
        current_version: app.package_info().version.to_string(),
        checked: state.checked.load(Ordering::Acquire),
        #[cfg(feature = "updater")]
        available_version: pending.as_ref().map(|update| update.version.clone()),
        #[cfg(not(feature = "updater"))]
        available_version: None,
        #[cfg(feature = "updater")]
        notes: pending
            .as_ref()
            .and_then(|update| update.body.as_ref())
            .map(|notes| notes.chars().take(8000).collect()),
        #[cfg(not(feature = "updater"))]
        notes: None,
    })
}

#[tauri::command]
pub(crate) fn app_update_status(
    app: AppHandle,
    state: State<'_, AppUpdater>,
) -> Result<AppUpdateStatus, String> {
    status(&app, &state)
}

#[tauri::command]
pub(crate) async fn check_app_update(
    app: AppHandle,
    state: State<'_, AppUpdater>,
) -> Result<AppUpdateStatus, String> {
    let _operation = state.begin()?;
    if !configured(&app) {
        return Err(NOT_CONFIGURED.to_string());
    }
    #[cfg(feature = "updater")]
    {
        let update = app
            .updater_builder()
            .timeout(Duration::from_secs(30))
            .configure_client(|client| client.https_only(true).no_proxy())
            .build()
            .map_err(|_| "업데이트 설정을 확인할 수 없습니다.")?
            .check()
            .await
            .map_err(|_| "업데이트를 확인하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.")?;
        if update
            .as_ref()
            .is_some_and(|update| !safe_https_url(update.download_url.as_str()))
        {
            return Err("업데이트 파일 주소가 안전한 HTTPS 주소가 아닙니다.".to_string());
        }
        *state
            .pending
            .lock()
            .map_err(|_| "업데이트 상태를 다시 확인해 주세요.")? = update;
        state.checked.store(true, Ordering::Release);
    }
    status(&app, &state)
}

#[cfg(feature = "updater")]
async fn download_package(url: &str, max_bytes: usize) -> Result<Vec<u8>, String> {
    let mut response = reqwest::Client::builder()
        // GitHub release downloads redirect to an HTTPS CDN. Never attach Core credentials.
        .redirect(reqwest::redirect::Policy::custom(|attempt| {
            if attempt.previous().len() <= 5 && safe_https_url(attempt.url().as_str()) {
                attempt.follow()
            } else {
                attempt.stop()
            }
        }))
        .no_proxy()
        .timeout(Duration::from_secs(600))
        .build()
        .map_err(|_| "업데이트 통신을 준비하지 못했습니다.")?
        .get(url)
        .send()
        .await
        .map_err(|_| "업데이트 다운로드가 중단되었습니다. 다시 확인해 주세요.")?;
    if !response.status().is_success()
        || response
            .content_length()
            .is_some_and(|size| size > max_bytes as u64)
    {
        return Err("업데이트 응답이나 파일 크기가 올바르지 않습니다.".to_string());
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| "업데이트 다운로드가 중단되었습니다.")?
    {
        if bytes.len().saturating_add(chunk.len()) > max_bytes {
            return Err("업데이트 파일이 허용 크기를 넘었습니다.".to_string());
        }
        if bytes.len() + chunk.len() > bytes.capacity() {
            let capacity = bytes
                .capacity()
                .max(64 * 1024)
                .saturating_mul(2)
                .max(bytes.len() + chunk.len())
                .min(max_bytes);
            bytes
                .try_reserve_exact(capacity - bytes.len())
                .map_err(|_| "업데이트 파일을 위한 메모리가 부족합니다.")?;
        }
        bytes.extend_from_slice(&chunk);
    }
    Ok(bytes)
}

#[tauri::command]
pub(crate) async fn install_app_update(
    app: AppHandle,
    state: State<'_, AppUpdater>,
    version: String,
    confirmed: bool,
) -> Result<(), String> {
    let _operation = state.begin()?;
    if !configured(&app) {
        return Err(NOT_CONFIGURED.to_string());
    }
    if !confirmed {
        return Err("업데이트 설치·재시작 확인이 필요합니다.".to_string());
    }
    #[cfg(feature = "updater")]
    {
        state.checked.store(false, Ordering::Release);
        let update = state
            .pending
            .lock()
            .map_err(|_| "업데이트 상태를 다시 확인해 주세요.")?
            .take()
            .filter(|update| update.version == version)
            .ok_or("설치할 버전을 다시 확인해 주세요.")?;
        if !safe_https_url(update.download_url.as_str()) {
            return Err("업데이트 파일 주소가 안전하지 않습니다.".to_string());
        }
        let bytes = download_package(update.download_url.as_str(), MAX_UPDATE_BYTES).await?;
        update
            .verify(&bytes)
            .map_err(|_| "업데이트 서명을 확인하지 못했습니다. 파일은 설치하지 않았습니다.")?;
        tauri::async_runtime::spawn_blocking(move || {
            let resource_dir = app
                .path()
                .resource_dir()
                .map_err(|_| "앱 경로를 확인하지 못했습니다.")?;
            app.state::<super::CoreProcessManager>()
                .install_application_update(&resource_dir, || {
                    update
                        .install(bytes)
                        .map_err(|_| "업데이트 설치를 완료하지 못했습니다.".to_string())
                })?;
            app.restart();
            #[allow(unreachable_code)]
            Ok::<(), String>(())
        })
        .await
        .map_err(|_| "업데이트 작업을 완료하지 못했습니다.")??;
    }
    #[cfg(not(feature = "updater"))]
    let _ = version;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_updates_require_secure_config_and_explicit_operation_serialization() {
        let mut config = serde_json::json!({"pubkey":"public fixture", "requireSignedVersion":true,
            "endpoints":["https://example.org/latest.json"]});
        assert!(trusted_config(Some(&config)));
        for field in [
            "allowDowngrades",
            "dangerousInsecureTransportProtocol",
            "dangerousAcceptInvalidCerts",
            "dangerousAcceptInvalidHostnames",
        ] {
            config[field] = true.into();
            assert!(!trusted_config(Some(&config)));
            config[field] = false.into();
        }
        config["endpoints"] = serde_json::json!(["https://user:secret@example.org"]);
        assert!(!trusted_config(Some(&config)));
        assert!(!trusted_config(None));
        let state = AppUpdater::default();
        let operation = state.begin().unwrap();
        assert!(state.begin().is_err());
        drop(operation);
        assert!(state.begin().is_ok());
    }
    #[cfg(feature = "updater")]
    fn verified_fixture() -> Update {
        // Public upstream tauri-plugin-updater2.14.1 offline vector; payload is just b"test".
        // No private key is generated, loaded or installed by these tests.
        let public_key = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEE0OUVGNDc0NkZBNkU2RDcKUldUWDVxWnZkUFNlcERHV2cyYno4bjZBclFuQk13Z1FLMWdlVm9zb3JjYkx6Y3VuRCtLSitjWWU=";
        let signature = "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkKUlVUWDVxWnZkUFNlcFBGMnpzanZQL0wvVFF0QkxSbldSdmFxKzRvbUsxVUV1Z3RRcC9VU3JHaUkxdjc2MnNEeTNpZDNhb3I3YlJDOUVUeWVvdDZsTUhIcldvWjVoalVNMVFjPQp0cnVzdGVkIGNvbW1lbnQ6IHRpbWVzdGFtcDoxNzkxNjQ5MDUxCWZpbGU6cGF5bG9hZAl2ZXJzaW9uOjIuMC4wCkREcTJDTE9FbDVjUW1DMmVKUkhsblpQVlZpT1pzdTFDanBQS1FvZWk0QS9YQmZrRHFHTzBCK1FNcmNySGdFUTVxVjNtbmU3NXRkRldoSnBxVVhoOUFBPT0=";
        let mut context = tauri::test::mock_context(tauri::test::noop_assets());
        context.config_mut().plugins.0.insert(
            "updater".into(),
            serde_json::json!({
                "pubkey": public_key, "requireSignedVersion":true,
                "endpoints":["https://example.invalid/latest.json"]
            }),
        );
        let app = tauri::test::mock_builder()
            .plugin(tauri_plugin_updater::Builder::new().build())
            .build(context)
            .unwrap();
        let updater = app
            .updater_builder()
            .target("fixture")
            .executable_path("fixture-runtime/app")
            .build()
            .unwrap();
        updater
            .restore_update(serde_json::json!({"version":"2.0.0", "platforms":{
                "fixture":{"url":"https://example.invalid/package", "signature":signature}
            }}))
            .unwrap()
            .unwrap()
    }

    #[cfg(feature = "updater")]
    #[test]
    fn verifies_real_public_signature_and_rejects_tampered_bytes_or_signature_before_install() {
        let update = verified_fixture();
        assert!(update.verify(b"test").is_ok());
        assert!(update.verify(b"tampered").is_err());
        assert!(update.install(b"tampered").is_err()); // Never reaches native installer.
        let mut wrong_version = update.clone();
        wrong_version.version = "3.0.0".into();
        assert!(wrong_version.verify(b"test").is_err());
        let mut bad_signature = update;
        bad_signature.signature = "invalid signature".into();
        assert!(bad_signature.verify(b"test").is_err());
    }

    #[cfg(feature = "updater")]
    #[test]
    fn interrupted_oversized_or_redirected_downloads_fail_without_installing() {
        use std::io::{Read, Write};
        use std::net::TcpListener;
        for (response, max_bytes) in [
            ("HTTP/1.1 200 OK\r\nContent-Length: 100\r\nConnection: close\r\n\r\ntest", 1024),
            ("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n01234567890123456789", 8),
            ("HTTP/1.1 302 Found\r\nContent-Length: 0\r\nLocation: http://example.invalid/never\r\n\r\n", 1024),
        ] {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let address = listener.local_addr().unwrap();
            let server = std::thread::spawn(move || {
                let (mut connection, _) = listener.accept().unwrap();
                let mut request = [0_u8; 2048];
                let _ = connection.read(&mut request);
                connection.write_all(response.as_bytes()).unwrap();
            });
            // Only this private transport helper is exercised with loopback HTTP fixtures.
            // Production commands reject non-HTTPS URLs before calling it.
            assert!(tauri::async_runtime::block_on(download_package(
                &format!("http://{address}/fixture"), max_bytes,
            )).is_err());
            server.join().unwrap();
        }
    }
}
