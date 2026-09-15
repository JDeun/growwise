from __future__ import annotations

from fastapi.testclient import TestClient

from growwise.api.main import app
from growwise.api.study_routes import get_study_store
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.storage import EntityStore


def _client(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    app.dependency_overrides[get_study_store] = lambda: store
    return TestClient(app), store


def test_study_tracking_vertical_slice_is_child_scoped_and_peer_free(tmp_path) -> None:
    client, store = _client(tmp_path)
    try:
        child = ChildProfile(nickname="중학생", stage=Stage.MIDDLE, age_months=168)
        other = ChildProfile(nickname="다른 아이", stage=Stage.HIGH, age_months=204)
        store.save(child)
        store.save(other)

        global_resource = ResourceRecord(
            kind=ResourceKind.NOTE,
            title="수학 일차함수 개념 정리",
            content="기울기와 절편을 그래프로 확인한다.",
            tags=["수학", "일차함수"],
        )
        private_other = ResourceRecord(
            child_id=other.id,
            kind=ResourceKind.NOTE,
            title="다른 아이의 일차함수 메모",
            content="private",
            tags=["수학", "일차함수"],
        )
        store.save(global_resource)
        store.save(private_other)

        progress = client.post(
            f"/v1/children/{child.id}/study/progress",
            json={
                "subject": "수학",
                "unit": "일차함수",
                "state": "revisit",
                "note": "그래프 해석을 다시 확인",
            },
        )
        assert progress.status_code == 200

        for response_text in ("x절편을 기울기로 착각", "기울기 부호를 반대로 설명"):
            response = client.post(
                f"/v1/children/{child.id}/study/mistakes",
                json={
                    "subject": "수학",
                    "unit": "일차함수",
                    "mistake_type": "concept",
                    "learner_response": response_text,
                    "corrected_understanding": "그래프에서 변화량을 다시 확인함",
                },
            )
            assert response.status_code == 200

        reflection = client.post(
            f"/v1/children/{child.id}/study/reflections",
            json={
                "subject": "수학",
                "unit": "일차함수",
                "worked_well": "그래프를 직접 그리면 이해가 잘 됨",
                "difficult_point": "식과 그래프를 바로 연결하는 부분이 헷갈림",
                "next_step": "두 표현을 번갈아 설명해 보기",
            },
        )
        assert reflection.status_code == 200

        explanation = client.post(
            f"/v1/children/{child.id}/study/self-explanations",
            json={
                "subject": "수학",
                "unit": "일차함수",
                "explanation": "기울기는 x가 1 변할 때 y가 얼마나 변하는지를 나타낸다.",
                "evidence_refs": [f"resource:{global_resource.id}"],
                "open_question": "절편이 바뀌면 그래프는 어떻게 이동하는가?",
            },
        )
        assert explanation.status_code == 200

        weak_map_response = client.get(f"/v1/children/{child.id}/study/weak-map")
        assert weak_map_response.status_code == 200
        weak_map = weak_map_response.json()
        assert weak_map["peer_comparison_used"] is False
        assert len(weak_map["entries"]) == 1
        entry = weak_map["entries"][0]
        assert entry["subject"] == "수학"
        assert entry["unit"] == "일차함수"
        assert entry["evidence_count"] == 4
        assert entry["recurring_mistake_types"] == ["concept"]
        assert entry["parent_support_points"]
        assert "점수" not in str(entry)
        assert "등수" not in str(entry)

        resources = client.get(
            f"/v1/children/{child.id}/study/resources",
            params={"subject": "수학", "unit": "일차함수"},
        )
        assert resources.status_code == 200
        resource_ids = {item["resource_id"] for item in resources.json()}
        assert str(global_resource.id) in resource_ids
        assert str(private_other.id) not in resource_ids

        plan = client.post(
            f"/v1/children/{child.id}/study/plans",
            json={
                "title": "중간고사 준비",
                "parent_note": "하루 분량 경쟁 없이 필요한 부분만 확인",
                "max_items": 4,
            },
        )
        assert plan.status_code == 200
        plan_payload = plan.json()
        assert len(plan_payload["items"]) == 1
        assert plan_payload["items"][0]["unit"] == "일차함수"
        assert "streak" not in plan_payload
        assert "rank" not in plan_payload

        persisted = store.index.list_entities(
            entity_type="self_explanation_log",
            child_id=str(child.id),
        )
        assert len(persisted) == 1
    finally:
        app.dependency_overrides.clear()


def test_study_tracking_rejects_non_secondary_stage(tmp_path) -> None:
    client, store = _client(tmp_path)
    try:
        child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=120)
        store.save(child)
        response = client.post(
            f"/v1/children/{child.id}/study/progress",
            json={"subject": "수학", "unit": "분수", "state": "in_progress"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "study_tracking_requires_middle_or_high_stage"
    finally:
        app.dependency_overrides.clear()
