from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected snippet not found in {path}: {old[:100]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Avoid collisions when multiple backups/restores happen in the same second.
replace_once(
    "src/growwise/backup/cli.py",
    '    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")\n',
    '    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")\n',
)
replace_once(
    "src/growwise/backup/service.py",
    '                f"{datetime.now(UTC).strftime(\'%Y%m%dT%H%M%SZ\')}"\n',
    '                f"{datetime.now(UTC).strftime(\'%Y%m%dT%H%M%S%fZ\')}"\n',
)

# Invalid arbitrary ZIPs are user errors, not Core 500s.
replace_once(
    "src/growwise/backup/service.py",
    '''            with zipfile.ZipFile(archive_path, "r") as archive:\n                manifest = self._read_manifest(archive)\n                self._validate_members(archive)\n                archive.extractall(staging)\n\n            staged_records = staging / "records"\n''',
    '''            try:\n                with zipfile.ZipFile(archive_path, "r") as archive:\n                    manifest = self._read_manifest(archive)\n                    self._validate_members(archive)\n                    archive.extractall(staging)\n            except zipfile.BadZipFile as exc:\n                raise InvalidBackup("backup archive is not a valid ZIP file") from exc\n\n            staged_records = staging / "records"\n''',
)

# Rust: native file dialogs + trusted managed-backup copy boundary.
replace_once(
    "desktop/src-tauri/src/lib.rs",
    '''use core_process::CoreProcessManager;\nuse serde::{Deserialize, Serialize};\nuse tauri::Manager;\n''',
    '''use std::fs;\nuse std::path::PathBuf;\nuse std::time::{SystemTime, UNIX_EPOCH};\n\nuse core_process::CoreProcessManager;\nuse serde::{Deserialize, Serialize};\nuse tauri::Manager;\nuse tauri_plugin_dialog::DialogExt;\n''',
)

portable_commands = r'''

fn backup_path_from_list(backups: &serde_json::Value, archive_name: &str) -> Result<PathBuf, String> {
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
async fn export_backup(
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
async fn import_backup(app: tauri::AppHandle) -> Result<Option<serde_json::Value>, String> {
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
'''

replace_once(
    "desktop/src-tauri/src/lib.rs",
    '''\n#[cfg_attr(mobile, tauri::mobile_entry_point)]\npub fn run() {\n''',
    portable_commands + '''\n#[cfg_attr(mobile, tauri::mobile_entry_point)]\npub fn run() {\n''',
)
replace_once(
    "desktop/src-tauri/src/lib.rs",
    '''    tauri::Builder::default()\n        .setup(|app| {\n''',
    '''    tauri::Builder::default()\n        .plugin(tauri_plugin_dialog::init())\n        .setup(|app| {\n''',
)
replace_once(
    "desktop/src-tauri/src/lib.rs",
    '''            list_backups,\n            create_backup,\n            restore_backup\n''',
    '''            list_backups,\n            create_backup,\n            restore_backup,\n            export_backup,\n            import_backup\n''',
)

# Frontend IPC surface.
replace_once(
    "desktop/src/api.ts",
    '''export const createBackup = () => call<BackupCreateResult>("create_backup");\nexport const restoreBackup = (archiveName: string) => call<BackupRestoreResult>("restore_backup", { archiveName });\n''',
    '''export const createBackup = () => call<BackupCreateResult>("create_backup");\nexport const restoreBackup = (archiveName: string) => call<BackupRestoreResult>("restore_backup", { archiveName });\nexport const exportBackup = (archiveName: string) => call<string | null>("export_backup", { archiveName });\nexport const importBackup = () => call<(BackupRestoreResult & { safety_backup: string; imported_archive: string }) | null>("import_backup");\n''',
)

# Desktop UI: import/export actions with explicit destructive confirmation.
replace_once(
    "desktop/src/App.tsx",
    '''  createResource,\n  generateMaterial,\n''',
    '''  createResource,\n  exportBackup,\n  generateMaterial,\n''',
)
replace_once(
    "desktop/src/App.tsx",
    '''  getInfantObservationHints,\n  listActivities,\n''',
    '''  getInfantObservationHints,\n  importBackup,\n  listActivities,\n''',
)
replace_once(
    "desktop/src/App.tsx",
    '''  async function handleRestoreBackup(archiveName: string) {\n''',
    '''  async function handleExportBackup(archiveName: string) {\n    setBackupBusy(true);\n    setBackupError(null);\n    try {\n      await exportBackup(archiveName);\n    } catch (error) {\n      setBackupError(error instanceof Error ? error.message : "백업 내보내기에 실패했습니다.");\n    } finally {\n      setBackupBusy(false);\n    }\n  }\n\n  async function handleImportBackup() {\n    const confirmed = window.confirm(\n      "외부 GrowWise ZIP을 가져오면 현재 기록을 교체합니다. 가져오기 직전에 현재 상태를 자동 보호 백업합니다. 계속할까요?",\n    );\n    if (!confirmed) return;\n    setBackupBusy(true);\n    setBackupError(null);\n    try {\n      const result = await importBackup();\n      if (result) await refresh();\n    } catch (error) {\n      setBackupError(error instanceof Error ? error.message : "외부 백업 가져오기에 실패했습니다.");\n    } finally {\n      setBackupBusy(false);\n    }\n  }\n\n  async function handleRestoreBackup(archiveName: string) {\n''',
)
replace_once(
    "desktop/src/App.tsx",
    '''          <button className="quiet-button" type="button" onClick={() => void handleCreateBackup()} disabled={!isConnected || backupBusy}>\n            {backupBusy ? "처리 중…" : "지금 백업"}\n          </button>\n''',
    '''          <div className="review-actions">\n            <button className="quiet-button" type="button" onClick={() => void handleImportBackup()} disabled={!isConnected || backupBusy}>\n              외부 ZIP 가져오기\n            </button>\n            <button className="quiet-button" type="button" onClick={() => void handleCreateBackup()} disabled={!isConnected || backupBusy}>\n              {backupBusy ? "처리 중…" : "지금 백업"}\n            </button>\n          </div>\n''',
)
replace_once(
    "desktop/src/App.tsx",
    '''                <button className="quiet-button" type="button" disabled={backupBusy} onClick={() => void handleRestoreBackup(backup.archive)}>이 백업 복원</button>\n''',
    '''                <div className="review-actions">\n                  <button className="quiet-button" type="button" disabled={backupBusy} onClick={() => void handleExportBackup(backup.archive)}>ZIP 내보내기</button>\n                  <button className="quiet-button" type="button" disabled={backupBusy} onClick={() => void handleRestoreBackup(backup.archive)}>이 백업 복원</button>\n                </div>\n''',
)

# Add regression tests for malformed external archives and backup-name collision resistance.
backup_test = Path("tests/test_backup.py")
text = backup_test.read_text(encoding="utf-8")
if "test_restore_rejects_non_zip_as_invalid_backup" not in text:
    text += '''\n\ndef test_restore_rejects_non_zip_as_invalid_backup(tmp_path) -> None:\n    from growwise.backup import InvalidBackup\n\n    archive = tmp_path / "not-a-backup.zip"\n    archive.write_text("not a zip", encoding="utf-8")\n    with pytest.raises(InvalidBackup, match="valid ZIP"):\n        BackupService().restore(\n            archive_path=archive,\n            records_root=tmp_path / "records",\n            index_path=tmp_path / "index.sqlite3",\n        )\n'''
    backup_test.write_text(text, encoding="utf-8")

backup_cli_test = Path("tests/test_backup_cli.py")
text = backup_cli_test.read_text(encoding="utf-8")
if "test_default_archive_names_do_not_collide_in_same_second" not in text:
    text += '''\n\ndef test_default_archive_names_do_not_collide_in_same_second() -> None:\n    from growwise.backup.cli import default_archive_name\n\n    first = default_archive_name()\n    second = default_archive_name()\n    assert first != second\n    assert first.startswith("growwise-") and first.endswith(".zip")\n'''
    backup_cli_test.write_text(text, encoding="utf-8")
