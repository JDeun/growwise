use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use tauri_plugin_dialog::DialogExt;

use super::{client, ensure_success, next_operation_key, CORE_BASE_URL};

const MAX_RECORD_EXPORT_BYTES: u64 = 600 * 1024 * 1024;

struct PendingExport(PathBuf);

impl Drop for PendingExport {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

fn export_file(destination: &Path) -> Result<(PendingExport, File), String> {
    let parent = destination
        .parent()
        .ok_or("저장 폴더를 확인할 수 없습니다.")?;
    let temporary = parent.join(format!(".{}.tmp", next_operation_key("export")));
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let file = options
        .open(&temporary)
        .map_err(|error| format!("내보내기 파일을 준비하지 못했습니다: {error}"))?;
    Ok((PendingExport(temporary), file))
}

fn commit_export(pending: &PendingExport, file: File, destination: &Path) -> Result<(), String> {
    file.sync_all()
        .map_err(|error| format!("내보내기 파일 동기화 실패: {error}"))?;
    drop(file);
    fs::rename(&pending.0, destination)
        .map_err(|error| format!("내보내기 파일 저장 실패: {error}"))?;
    #[cfg(unix)]
    File::open(destination.parent().ok_or("저장 폴더가 없습니다.")?)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| {
            format!("파일은 저장되었지만 저장 폴더의 디스크 동기화를 확인하지 못했습니다: {error}")
        })?;
    Ok(())
}

fn zip_destination(mut path: PathBuf) -> PathBuf {
    if !path
        .extension()
        .and_then(|value| value.to_str())
        .is_some_and(|value| value.eq_ignore_ascii_case("zip"))
    {
        path.set_extension("zip");
    }
    path
}

fn record_export_url(
    base_url: &str,
    child_id: &str,
    start: Option<&str>,
    end: Option<&str>,
) -> Result<reqwest::Url, String> {
    let valid_child = child_id.len() == 36
        && child_id.bytes().enumerate().all(|(index, value)| {
            if [8, 13, 18, 23].contains(&index) {
                value == b'-'
            } else {
                value.is_ascii_hexdigit()
            }
        });
    if !valid_child {
        return Err("내보낼 아이를 먼저 선택해 주세요.".to_string());
    }
    for value in [start, end].into_iter().flatten() {
        if value.len() != 10
            || !value.bytes().enumerate().all(|(index, byte)| {
                if [4, 7].contains(&index) {
                    byte == b'-'
                } else {
                    byte.is_ascii_digit()
                }
            })
        {
            return Err("날짜는 YYYY-MM-DD 형식으로 입력해 주세요.".to_string());
        }
    }
    if matches!((start, end), (Some(first), Some(last)) if first > last) {
        return Err("종료일은 시작일 이후로 선택해 주세요.".to_string());
    }
    let mut url = reqwest::Url::parse(&format!("{base_url}/v1/children/{child_id}/records/export"))
        .map_err(|_| "기록 내보내기 경로를 준비하지 못했습니다.".to_string())?;
    if let Some(value) = start {
        url.query_pairs_mut().append_pair("start_date", value);
    }
    if let Some(value) = end {
        url.query_pairs_mut().append_pair("end_date", value);
    }
    Ok(url)
}

fn export_filename(response: &reqwest::Response) -> String {
    response
        .headers()
        .get(reqwest::header::CONTENT_DISPOSITION)
        .and_then(|header| header.to_str().ok())
        .and_then(|value| {
            value
                .split(';')
                .find_map(|part| part.trim().strip_prefix("filename="))
        })
        .map(|value| value.trim_matches('"'))
        .filter(|value| {
            value.starts_with("growwise-records-")
                && value.ends_with(".zip")
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || b"-_.".contains(&byte))
        })
        .unwrap_or("growwise-records.zip")
        .to_string()
}

fn write_record_chunk(
    file: &mut File,
    bytes: &mut u64,
    signature: &mut Vec<u8>,
    chunk: &[u8],
) -> Result<(), String> {
    *bytes = bytes
        .checked_add(chunk.len() as u64)
        .filter(|total| *total <= MAX_RECORD_EXPORT_BYTES)
        .ok_or("내보내기 ZIP이 600MiB를 넘습니다. 기간을 줄여 다시 시도해 주세요.")?;
    signature.extend(chunk.iter().take(4 - signature.len()).copied());
    if signature.len() == 4 && signature.as_slice() != b"PK\x03\x04" {
        return Err("기록 내보내기 ZIP이 올바르지 않습니다.".to_string());
    }
    file.write_all(chunk)
        .map_err(|error| format!("ZIP 파일 쓰기 실패: {error}"))
}

#[tauri::command]
pub(crate) async fn export_child_records(
    app: tauri::AppHandle,
    child_id: String,
    start_date: Option<String>,
    end_date: Option<String>,
) -> Result<Option<String>, String> {
    let url = record_export_url(
        &CORE_BASE_URL.to_string(),
        &child_id,
        start_date.as_deref(),
        end_date.as_deref(),
    )?;
    let mut response = ensure_success(
        client()?
            .get(url)
            .timeout(std::time::Duration::from_secs(600))
            .send()
            .await
            .map_err(|error| format!("기록 내보내기 요청 실패: {error}"))?,
        "기록 내보내기 실패",
    )
    .await?;
    if response
        .content_length()
        .is_some_and(|length| length > MAX_RECORD_EXPORT_BYTES)
    {
        return Err(
            "내보내기 ZIP이 600MiB를 넘습니다. 기간을 줄여 다시 시도해 주세요.".to_string(),
        );
    }
    if response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.split(';').next())
        != Some("application/zip")
    {
        return Err("기록 내보내기 응답이 ZIP 형식이 아닙니다.".to_string());
    }
    let filename = export_filename(&response);
    // Complete the bounded network operation before waiting for a person in the save dialog.
    // A private OS-temp file keeps RAM bounded and is removed on cancellation or any error.
    let (download, mut file) = export_file(&std::env::temp_dir().join("growwise-records.zip"))?;
    let mut bytes = 0_u64;
    let mut signature = Vec::with_capacity(4);
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|error| format!("ZIP 다운로드 실패: {error}"))?
    {
        write_record_chunk(&mut file, &mut bytes, &mut signature, &chunk)?;
    }
    if signature.len() < 4 {
        return Err("내보내기 ZIP이 비어 있거나 잘렸습니다.".to_string());
    }
    file.sync_all()
        .map_err(|error| format!("ZIP 임시 파일 동기화 실패: {error}"))?;
    drop(file);
    drop(response);
    let selected = tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("GrowWise 선택 기록 내보내기")
            .set_file_name(&filename)
            .add_filter("Markdown records ZIP", &["zip"])
            .blocking_save_file()
    })
    .await
    .map_err(|_| "저장 창을 열지 못했습니다.".to_string())?;
    let Some(selected) = selected else {
        return Ok(None);
    };
    let destination = zip_destination(
        selected
            .into_path()
            .map_err(|error| format!("저장 경로를 사용할 수 없습니다: {error}"))?,
    );
    tauri::async_runtime::spawn_blocking(move || {
        let (pending, mut output) = export_file(&destination)?;
        std::io::copy(
            &mut File::open(&download.0).map_err(|error| error.to_string())?,
            &mut output,
        )
        .map_err(|error| format!("ZIP 파일 복사 실패: {error}"))?;
        commit_export(&pending, output, &destination)?;
        drop(download);
        Ok(Some(destination.display().to_string()))
    })
    .await
    .map_err(|_| "ZIP 저장 작업을 완료하지 못했습니다.".to_string())?
}

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
    let destination = selected
        .into_path()
        .map_err(|error| format!("선택한 저장 경로를 사용할 수 없습니다: {error}"))?;
    let destination = zip_destination(destination);
    if source != destination {
        let (pending, mut output) = export_file(&destination)?;
        std::io::copy(
            &mut File::open(&source).map_err(|error| error.to_string())?,
            &mut output,
        )
        .map_err(|error| format!("백업 파일 내보내기에 실패했습니다: {error}"))?;
        commit_export(&pending, output, &destination)?;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selected_export_routes_only_the_chosen_uuid_and_present_dates() {
        let child = "019b2abe-1111-7111-8111-111111111111";
        let url =
            record_export_url("http://127.0.0.1:8080", child, Some("2026-01-01"), None).unwrap();
        assert_eq!(url.path(), format!("/v1/children/{child}/records/export"));
        assert_eq!(url.query(), Some("start_date=2026-01-01"));
        assert!(
            record_export_url("http://127.0.0.1:8080", child, None, None)
                .unwrap()
                .query()
                .is_none()
        );
        assert!(
            record_export_url("http://127.0.0.1:8080", "../another-child", None, None).is_err()
        );
        assert!(record_export_url(
            "http://127.0.0.1:8080",
            child,
            Some("2026-11-04"),
            Some("2026-11-03")
        )
        .is_err());
        assert!(
            record_export_url("http://127.0.0.1:8080", child, Some("2026&other=1"), None).is_err()
        );
    }

    #[test]
    fn atomic_exports_preserve_existing_files_until_a_complete_commit_and_clean_partial_files() {
        let root = std::env::temp_dir().join(next_operation_key("export-test"));
        fs::create_dir_all(&root).unwrap();
        let destination = root.join("selected.zip");
        fs::write(&destination, b"previous export").unwrap();
        {
            let (_pending, mut output) = export_file(&destination).unwrap();
            output.write_all(b"partial new export").unwrap();
        }
        assert_eq!(fs::read(&destination).unwrap(), b"previous export");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);
        let (pending, mut output) = export_file(&destination).unwrap();
        output.write_all(b"PK\x03\x04complete export").unwrap();
        commit_export(&pending, output, &destination).unwrap();
        drop(pending);
        assert_eq!(
            fs::read(&destination).unwrap(),
            b"PK\x03\x04complete export"
        );
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(
                fs::metadata(&destination).unwrap().permissions().mode() & 0o777,
                0o600
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn record_download_rejects_oversized_or_malformed_chunks_without_replacing_existing_export() {
        let root = std::env::temp_dir().join(next_operation_key("export-bounds-test"));
        fs::create_dir_all(&root).unwrap();
        let destination = root.join("records.zip");
        fs::write(&destination, b"previous export").unwrap();
        {
            let (_pending, mut output) = export_file(&destination).unwrap();
            let mut count = MAX_RECORD_EXPORT_BYTES;
            let mut signature = b"PK\x03\x04".to_vec();
            assert!(write_record_chunk(&mut output, &mut count, &mut signature, b"x").is_err());
        }
        {
            let (_pending, mut output) = export_file(&destination).unwrap();
            let mut count = 0;
            let mut signature = Vec::new();
            write_record_chunk(&mut output, &mut count, &mut signature, b"P").unwrap();
            assert!(write_record_chunk(&mut output, &mut count, &mut signature, b"oops").is_err());
        }
        assert_eq!(fs::read(&destination).unwrap(), b"previous export");
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);
        fs::remove_dir_all(root).unwrap();
    }
}
