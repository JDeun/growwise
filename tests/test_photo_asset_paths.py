import base64
from uuid import UUID

import pytest

from growwise.services.photo_activity import PhotoAssetStore, PhotoUpload, PhotoValidationError

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
CHILD = UUID("018f47f2-9786-7c99-bc1f-1d5df10c0000")


@pytest.mark.parametrize("child_id", ["../escape", "/tmp/escape", "", "C:\\escape", f"{CHILD}/.."])
def test_low_level_store_and_delete_reject_non_uuid_before_filesystem_io(tmp_path, child_id):
    root = tmp_path / "assets"
    store = PhotoAssetStore(root, max_file_bytes=1024)
    with pytest.raises(PhotoValidationError, match="invalid_child_id"):
        store.store(child_id=child_id, upload=PhotoUpload("photo.png", "image/png", PNG))
    with pytest.raises(PhotoValidationError, match="invalid_child_id"):
        store.delete_child(child_id)
    assert not root.exists()


def test_low_level_store_canonicalizes_uuid_for_path_and_metadata(tmp_path):
    store = PhotoAssetStore(tmp_path, max_file_bytes=1024)
    asset, created = store.store(
        child_id=CHILD.hex.upper(), upload=PhotoUpload("photo.png", "image/png", PNG)
    )
    assert created
    assert asset.child_id == CHILD
    assert asset.relative_path.startswith(f"photos/{CHILD}/")
    assert store.read_verified(asset) == PNG
    assert store.delete_child(CHILD.hex.upper()) == 1


@pytest.mark.parametrize("component", ["namespace", "child", "file"])
def test_low_level_store_rejects_symlink_destination_and_preserves_external_files(
    tmp_path, component
):
    root = tmp_path / "assets"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "untouched.txt"
    sentinel.write_text("synthetic private file")
    store = PhotoAssetStore(root, max_file_bytes=1024)
    if component == "namespace":
        link = root / "photos"
    elif component == "child":
        link = root / "photos" / str(CHILD)
    else:
        import hashlib

        link = root / "photos" / str(CHILD) / f"{hashlib.sha256(PNG).hexdigest()}.png"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(
            sentinel if component == "file" else outside, target_is_directory=component != "file"
        )
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    with pytest.raises(PhotoValidationError, match="unsafe_photo_path"):
        store.store(child_id=str(CHILD), upload=PhotoUpload("photo.png", "image/png", PNG))
    if component != "file":
        with pytest.raises(PhotoValidationError, match="unsafe_photo_path"):
            store.delete_child(str(CHILD))
    assert sentinel.read_text() == "synthetic private file"
    assert list(outside.iterdir()) == [sentinel]
