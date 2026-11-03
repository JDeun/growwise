use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use tauri::Manager;
use tauri_plugin_dialog::DialogExt;

use super::core_process::CoreProcessManager;

const LOCATION_FILE: &str = "storage-location.json";

pub(crate) fn configured_data_dir(default: &Path) -> Result<PathBuf, String> {
    let file = default.join(LOCATION_FILE);
    if !file.exists() {
        return Ok(default.to_path_buf());
    }
    let path: PathBuf = serde_json::from_slice(&fs::read(file).map_err(|error| error.to_string())?)
        .map_err(|error| format!("저장 위치 설정이 손상되었습니다: {error}"))?;
    if !path.is_absolute() || !path.is_dir() {
        return Err("저장 폴더를 찾을 수 없습니다. 외장 디스크 연결을 확인해 주세요.".to_string());
    }
    Ok(path)
}

fn sync_directory(path: &Path) -> std::io::Result<()> {
    #[cfg(unix)]
    File::open(path)?.sync_all()?;
    // Windows does not expose directory fsync through std::fs::File.
    #[cfg(not(unix))]
    let _ = path;
    Ok(())
}

fn committed_location_warning(result: std::io::Result<()>) -> Option<String> {
    result.err().map(|error| format!(
        "새 저장소로 연결했지만 저장 위치 설정의 디스크 동기화를 확인하지 못했습니다: {error}. 원본 사본을 보존하고 백업을 만들어 주세요."
    ))
}

pub(crate) fn save_location(file: &Path, path: &Path) -> Result<Option<String>, String> {
    save_location_with_sync(file, path, sync_directory)
}

fn save_location_with_sync(
    file: &Path,
    path: &Path,
    sync_parent: impl FnOnce(&Path) -> std::io::Result<()>,
) -> Result<Option<String>, String> {
    let parent = file.parent().ok_or("저장 위치 설정 폴더가 없습니다.")?;
    let temporary = file.with_extension("json.tmp");
    let result = (|| -> Result<(), String> {
        let mut output = File::create(&temporary).map_err(|error| error.to_string())?;
        output
            .write_all(&serde_json::to_vec(path).map_err(|error| error.to_string())?)
            .map_err(|error| error.to_string())?;
        output.sync_all().map_err(|error| error.to_string())?;
        fs::rename(&temporary, file).map_err(|error| error.to_string())?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(temporary);
    }
    result?;
    // The pointer has committed; a later durability failure must not restart the old store.
    Ok(committed_location_warning(sync_parent(parent)))
}

pub(crate) fn validate_destination(source: &Path, destination: &Path) -> Result<PathBuf, String> {
    let source = source.canonicalize().map_err(|error| error.to_string())?;
    let destination = destination
        .canonicalize()
        .map_err(|error| error.to_string())?;
    if !destination.is_dir() || destination.starts_with(&source) || source.starts_with(&destination)
    {
        return Err("현재 저장소와 겹치지 않는 빈 폴더를 선택해 주세요.".to_string());
    }
    if fs::read_dir(&destination)
        .map_err(|error| error.to_string())?
        .next()
        .is_some()
    {
        return Err("새 저장 폴더는 비어 있어야 합니다.".to_string());
    }
    Ok(destination)
}

fn identical(left: &Path, right: &Path) -> std::io::Result<bool> {
    let mut left = File::open(left)?;
    let mut right = File::open(right)?;
    let mut a = [0_u8; 65536];
    let mut b = [0_u8; 65536];
    loop {
        let size = left.read(&mut a)?;
        right.read_exact(&mut b[..size])?;
        if a[..size] != b[..size] {
            return Ok(false);
        }
        if size == 0 {
            return Ok(right.read(&mut b)? == 0);
        }
    }
}

pub(crate) fn copy_data_directory(source: &Path, destination: &Path) -> Result<(), String> {
    fn copy_tree(source: &Path, destination: &Path) -> std::io::Result<()> {
        fs::set_permissions(destination, fs::metadata(source)?.permissions())?;
        for entry in fs::read_dir(source)? {
            let entry = entry?;
            if entry.file_name() == ".core.lock" || entry.file_name() == LOCATION_FILE {
                continue;
            }
            let target = destination.join(entry.file_name());
            let kind = entry.file_type()?;
            if kind.is_dir() {
                fs::create_dir(&target)?;
                copy_tree(&entry.path(), &target)?;
            } else if kind.is_file() {
                let mut output = File::options().write(true).create_new(true).open(&target)?;
                std::io::copy(&mut File::open(entry.path())?, &mut output)?;
                fs::set_permissions(&target, entry.metadata()?.permissions())?;
                output.sync_all()?;
                if !identical(&entry.path(), &target)? {
                    return Err(std::io::Error::other("저장소 복사 검증에 실패했습니다."));
                }
            } else {
                return Err(std::io::Error::other(
                    "저장소의 심볼릭 링크/특수 파일은 이전할 수 없습니다.",
                ));
            }
        }
        sync_directory(destination)
    }
    (|| -> std::io::Result<()> {
        copy_tree(source, destination)?;
        // The disposable projection stores absolute Markdown source_path values. Its first
        // destination-side EntityStore must rebuild them before it can serve or repair records.
        // Use the Core's durable recovery protocol instead of changing SQLite from Desktop.
        let mut dirty = File::create(destination.join("index.sqlite3.dirty"))?;
        dirty.write_all(b"dirty\n")?;
        dirty.sync_all()?;
        sync_directory(destination)
    })()
    .map_err(|error| format!("저장소 이전 실패 (원본 보존): {error}"))
}

#[tauri::command]
pub(crate) fn get_storage_location(
    manager: tauri::State<'_, CoreProcessManager>,
) -> Result<String, String> {
    Ok(manager.data_dir()?.to_string_lossy().into_owned())
}

#[tauri::command]
pub(crate) async fn choose_storage_location(
    app: tauri::AppHandle,
) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        app.dialog()
            .file()
            .set_title("GrowWise 새 저장 폴더 (빈 폴더)")
            .blocking_pick_folder()
            .map(|selected| {
                selected
                    .into_path()
                    .map(|path| path.to_string_lossy().into_owned())
                    .map_err(|error| error.to_string())
            })
            .transpose()
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
pub(crate) async fn relocate_storage(
    app: tauri::AppHandle,
    destination: String,
) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let manager = app.state::<CoreProcessManager>();
        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| error.to_string())?;
        let location_file = app
            .path()
            .app_data_dir()
            .map_err(|error| error.to_string())?
            .join(LOCATION_FILE);
        manager.relocate(&resource_dir, Path::new(&destination), &location_file)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temporary_root() -> PathBuf {
        static NEXT_ROOT: AtomicU64 = AtomicU64::new(0);
        std::env::temp_dir().join(format!(
            "growwise-storage-{}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos(),
            NEXT_ROOT.fetch_add(1, Ordering::Relaxed)
        ))
    }

    #[test]
    fn committed_pointer_durability_failure_keeps_new_location_and_returns_warning() {
        let root = temporary_root();
        let destination = root.join("destination");
        fs::create_dir_all(&destination).unwrap();
        let pointer = root.join(LOCATION_FILE);
        let warning = save_location_with_sync(&pointer, &destination, |_| {
            Err(std::io::Error::other("injected directory flush failure"))
        })
        .unwrap();
        assert!(warning
            .unwrap()
            .contains("injected directory flush failure"));
        assert_eq!(configured_data_dir(&root).unwrap(), destination);
        assert!(!pointer.with_extension("json.tmp").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_pointer_write_leaves_previous_selection_untouched() {
        let root = temporary_root();
        let source = root.join("source");
        let destination = root.join("destination");
        fs::create_dir_all(&source).unwrap();
        fs::create_dir_all(&destination).unwrap();
        let pointer = root.join(LOCATION_FILE);
        save_location(&pointer, &source).unwrap();
        fs::create_dir(pointer.with_extension("json.tmp")).unwrap();
        assert!(save_location(&pointer, &destination).is_err());
        assert_eq!(configured_data_dir(&root).unwrap(), source);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn partial_copy_never_overwrites_an_existing_destination_file() {
        let root = temporary_root();
        let source = root.join("source");
        let destination = root.join("destination");
        fs::create_dir_all(&source).unwrap();
        fs::create_dir_all(&destination).unwrap();
        fs::write(source.join("record.md"), b"source").unwrap();
        fs::write(destination.join("record.md"), b"existing").unwrap();
        assert!(copy_data_directory(&source, &destination).is_err());
        assert_eq!(fs::read(source.join("record.md")).unwrap(), b"source");
        assert_eq!(
            fs::read(destination.join("record.md")).unwrap(),
            b"existing"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn copy_preserves_private_permissions_and_rejects_symlinks() {
        use std::os::unix::fs::{symlink, PermissionsExt};
        let root = temporary_root();
        let source = root.join("source");
        let destination = root.join("destination");
        fs::create_dir_all(&source).unwrap();
        fs::create_dir_all(&destination).unwrap();
        fs::set_permissions(&source, fs::Permissions::from_mode(0o700)).unwrap();
        fs::write(source.join("record.md"), b"private").unwrap();
        fs::set_permissions(source.join("record.md"), fs::Permissions::from_mode(0o600)).unwrap();
        copy_data_directory(&source, &destination).unwrap();
        assert_eq!(
            fs::metadata(&destination).unwrap().permissions().mode() & 0o777,
            0o700
        );
        assert_eq!(
            fs::metadata(destination.join("record.md"))
                .unwrap()
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        let linked_source = root.join("linked-source");
        let rejected_destination = root.join("rejected-destination");
        fs::create_dir_all(&linked_source).unwrap();
        fs::create_dir_all(&rejected_destination).unwrap();
        symlink(source.join("record.md"), linked_source.join("outside.md")).unwrap();
        assert!(copy_data_directory(&linked_source, &rejected_destination).is_err());
        assert!(!rejected_destination.join("outside.md").exists());
        assert_eq!(fs::read(source.join("record.md")).unwrap(), b"private");
        assert!(sync_directory(&root.join("missing")).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn copies_whole_data_and_preserves_original_then_persists_selection() {
        let root = temporary_root();
        let source = root.join("source");
        let destination = root.join("destination");
        fs::create_dir_all(source.join("assets/photos")).unwrap();
        fs::create_dir_all(&destination).unwrap();
        for file in [
            "records.md",
            "index.sqlite3-wal",
            "conversations.sqlite3",
            "assets/photos/test.png",
        ] {
            fs::write(source.join(file), file.as_bytes()).unwrap();
        }
        assert!(validate_destination(&source, &source).is_err());
        assert!(validate_destination(&source, &source.join("assets")).is_err());
        let destination = validate_destination(&source, &destination).unwrap();
        copy_data_directory(&source, &destination).unwrap();
        assert!(source.join("records.md").exists());
        assert_eq!(
            fs::read(destination.join("index.sqlite3.dirty")).unwrap(),
            b"dirty\n"
        );
        assert!(!source.join("index.sqlite3.dirty").exists());
        assert!(identical(
            &source.join("assets/photos/test.png"),
            &destination.join("assets/photos/test.png")
        )
        .unwrap());
        assert!(validate_destination(&source, &destination).is_err());
        save_location(&source.join(LOCATION_FILE), &destination).unwrap();
        assert_eq!(configured_data_dir(&source).unwrap(), destination);
        fs::remove_dir_all(root).unwrap();
    }
}
