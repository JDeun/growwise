use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use tauri_plugin_dialog::DialogExt;

use super::{client, ensure_success, CORE_BASE_URL};

#[tauri::command]
pub(crate) async fn list_backups() -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!("{CORE_BASE_URL}/v1/admin/backups"))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 목록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn create_backup() -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!("{CORE_BASE_URL}/v1/admin/backups"))
        .json(&serde_json::json!({}))
        .timeout(std::time::Duration::from_secs(600))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 생성 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub(crate) async fn restore_backup(archive_name: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .post(format!(
            "{CORE_BASE_URL}/v1/admin/backups/{archive_name}/restore"
        ))
        .json(&serde_json::json!({"confirmed": true}))
        .timeout(std::time::Duration::from_secs(600))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "백업 복원 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

fn backup_path_from_list(
    backups: &serde_json::Value,
    archive_name: &str,
) -> Result<PathBuf, String> {
    let items = backups
        .as_array()
        .ok_or_else(|| "백업 목록 응답 형식이 올바르지 않습니다.".to_string())?;
    let item = items
        .iter()
        .find(|item| item.get("archive").and_then(serde_json::Value::as_str) == Some(archive_name))
        .ok_or_else(|| "내보낼 백업을 찾을 수 없습니다.".to_string())?;
    let path = item
        .get("path")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| "백업 경로가 없습니다.".to_string())?;
    let path = PathBuf::from(path);
    if !path.is_file() {
        return Err("백업 파일이 디스크에 없습니다.".to_string());
    }
    Ok(path)
}

fn json_string(value: &serde_json::Value, key: &str) -> Result<String, String> {
    value
        .get(key)
        .and_then(serde_json::Value::as_str)
        .map(ToOwned::to_owned)
        .ok_or_else(|| format!("백업 응답에 {key} 값이 없습니다."))
}

#[tauri::command]
pub(crate) async fn export_backup(
    app: tauri::AppHandle,
    archive_name: String,
) -> Result<Option<String>, String> {
    let backups = list_backups().await?;
    let source = backup_path_from_list(&backups, &archive_name)?;
    let selected = app
        .dialog()
        .file()
        .set_title("GrowWise 백업 내보내기")
        .set_file_name(&archive_name)
        .add_filter("GrowWise backup", &["zip"])
        .blocking_save_file();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let mut destination = selected
        .into_path()
        .map_err(|error| format!("선택한 저장 경로를 사용할 수 없습니다: {error}"))?;
    let has_zip_extension = destination
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("zip"))
        .unwrap_or(false);
    if !has_zip_extension {
        destination.set_extension("zip");
    }
    if source != destination {
        fs::copy(&source, &destination)
            .map_err(|error| format!("백업 파일 내보내기에 실패했습니다: {error}"))?;
    }
    Ok(Some(destination.display().to_string()))
}

#[tauri::command]
pub(crate) async fn import_backup(
    app: tauri::AppHandle,
) -> Result<Option<serde_json::Value>, String> {
    let selected = app
        .dialog()
        .file()
        .set_title("GrowWise 백업 가져오기")
        .add_filter("GrowWise backup", &["zip"])
        .blocking_pick_file();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let source = selected
        .into_path()
        .map_err(|error| format!("선택한 백업 경로를 사용할 수 없습니다: {error}"))?;
    if !source.is_file() {
        return Err("선택한 백업 파일을 찾을 수 없습니다.".to_string());
    }
    let is_zip = source
        .extension()
        .and_then(|extension| extension.to_str())
        .map(|extension| extension.eq_ignore_ascii_case("zip"))
        .unwrap_or(false);
    if !is_zip {
        return Err("GrowWise 백업은 .zip 파일이어야 합니다.".to_string());
    }

    // Always preserve the current state before attempting an external restore.
    let safety_backup = create_backup().await?;
    let safety_archive = json_string(&safety_backup, "archive")?;
    let safety_path = PathBuf::from(json_string(&safety_backup, "path")?);
    let backup_dir = safety_path
        .parent()
        .ok_or_else(|| "관리 백업 폴더를 확인할 수 없습니다.".to_string())?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("시스템 시간을 확인할 수 없습니다: {error}"))?
        .as_nanos();
    let imported_archive = format!("growwise-import-{stamp}.zip");
    let managed_copy = backup_dir.join(&imported_archive);
    fs::copy(&source, &managed_copy)
        .map_err(|error| format!("선택한 백업을 안전 영역으로 복사하지 못했습니다: {error}"))?;

    match restore_backup(imported_archive.clone()).await {
        Ok(mut result) => {
            if let Some(object) = result.as_object_mut() {
                object.insert(
                    "safety_backup".to_string(),
                    serde_json::Value::String(safety_archive),
                );
                object.insert(
                    "imported_archive".to_string(),
                    serde_json::Value::String(imported_archive),
                );
            }
            Ok(Some(result))
        }
        Err(error) => {
            let _ = fs::remove_file(&managed_copy);
            Err(format!(
                "외부 백업을 복원하지 못했습니다. 현재 상태 보호 백업({safety_archive})은 유지됩니다: {error}"
            ))
        }
    }
}
