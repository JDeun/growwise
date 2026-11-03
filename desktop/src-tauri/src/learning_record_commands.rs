use serde::{Deserialize, Serialize};

use super::{client, ensure_success, post_idempotent_json, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
pub struct LearningRecordRequest {
    kind: String,
    title: String,
    occurred_at: Option<String>,
    subject: Option<String>,
    institution: Option<String>,
    summary: String,
    learner_work: Option<String>,
    book_id: Option<String>,
    ai_hint: Option<String>,
    evidence_checked: Option<bool>,
    child_reexplanation: Option<String>,
    process: Option<String>,
    interest: Option<String>,
    difficulty_note: Option<String>,
    next_activity: Option<String>,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    shared_child_ids: Vec<String>,
}

#[tauri::command]
pub async fn create_learning_record(
    child_id: String,
    request: LearningRecordRequest,
) -> Result<serde_json::Value, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/children/{child_id}/learning-records"),
        &body,
        "learning-record",
    )
    .await?;
    ensure_success(response, "학습 기록 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn list_learning_records(child_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/children/{child_id}/learning-records"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "학습 기록 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::LearningRecordRequest;
    use serde_json::json;

    #[test]
    fn optional_evidence_preserves_legacy_unknown_and_explicit_false() {
        let legacy = json!({"kind":"reading_reflection", "title":"독서", "summary":"관찰",
            "tags":[], "experience_axes":[], "shared_child_ids":[]});
        let old: LearningRecordRequest = serde_json::from_value(legacy.clone()).unwrap();
        assert_eq!(old.evidence_checked, None);
        let mut with_evidence = legacy;
        with_evidence["book_id"] = json!("00000000-0000-0000-0000-000000000001");
        with_evidence["ai_hint"] = json!("힌트");
        with_evidence["evidence_checked"] = json!(false);
        with_evidence["child_reexplanation"] = json!("자기 설명");
        let parsed: LearningRecordRequest = serde_json::from_value(with_evidence).unwrap();
        let forwarded = serde_json::to_value(parsed).unwrap();
        assert_eq!(forwarded["evidence_checked"], false);
        assert_eq!(forwarded["ai_hint"], "힌트");
        assert_eq!(forwarded["child_reexplanation"], "자기 설명");
        assert_eq!(forwarded["book_id"], "00000000-0000-0000-0000-000000000001");
    }
}
