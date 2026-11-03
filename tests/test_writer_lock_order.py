import threading
from pathlib import Path
from time import monotonic, sleep

import pytest

from growwise.api.child_profile_routes import delete_child_avatar
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, MaterialStatus, Stage
from growwise.maintenance import DATA_MAINTENANCE
from growwise.services.child_lock import child_operation_lock
from growwise.services.material_quest import ensure_material_quest
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore


@pytest.mark.parametrize("operation", ["delete_avatar", "material_quest"])
def test_child_writers_register_before_waiting_for_child_lock(
    tmp_path: Path, operation: str
) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="테스트아이", stage=Stage.ELEMENTARY)
    store.save(child)
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.READING_ACTIVITY,
        title="읽기",
        content_markdown="활동",
        generator_mode="template",
        status=MaterialStatus.APPROVED,
    )
    store.save(material)
    child_lock = child_operation_lock(str(child.id))
    baseline = DATA_MAINTENANCE._active_mutations
    errors: list[Exception] = []

    def write() -> None:
        try:
            if operation == "delete_avatar":
                delete_child_avatar(child.id, settings, store)
            else:
                ensure_material_quest(store=store, material=material)
        except Exception as exc:
            errors.append(exc)

    def purge() -> None:
        try:
            ChildPurgeService(settings).purge(str(child.id))
        except Exception as exc:
            errors.append(exc)

    child_lock.acquire()
    writer = threading.Thread(target=write, daemon=True)
    purger = threading.Thread(target=purge, daemon=True)
    writer.start()
    try:
        deadline = monotonic() + 2
        while DATA_MAINTENANCE._active_mutations == baseline and monotonic() < deadline:
            sleep(0.01)
        assert DATA_MAINTENANCE._active_mutations == baseline + 1
        purger.start()
    finally:
        child_lock.release()
        writer.join(timeout=5)
        if purger.ident is not None:
            purger.join(timeout=5)
    assert not writer.is_alive()
    assert not purger.is_alive()
    assert errors == []
    fresh = EntityStore(settings.records_dir, settings.index_path)
    assert fresh.index.get_entity(str(child.id), entity_type="child_profile") is None
