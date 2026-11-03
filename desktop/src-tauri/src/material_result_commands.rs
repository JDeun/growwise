use serde::{Deserialize, Serialize};

use super::{client, ensure_success, post_idempotent_json, CORE_BASE_URL};

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct MaterialResultRequest {
    outcome: String,
    observation: String,
    learner_work: Option<String>,
    book_id: Option<String>,
    ai_hint: Option<String>,
    evidence_checked: Option<bool>,
    child_reexplanation: Option<String>,
    process: Option<String>,
    child_question: Option<String>,
    interest: Option<String>,
    difficulty_note: Option<String>,
    next_activity: Option<String>,
    tags: Vec<String>,
    experience_axes: Vec<String>,
    activity_plan_id: Option<String>,
    #[serde(default)]
    photo_record_ids: Vec<String>,
}

#[tauri::command]
pub async fn record_material_result(
    material_id: String,
    request: MaterialResultRequest,
) -> Result<serde_json::Value, String> {
    let body = serde_json::to_value(&request).map_err(|error| error.to_string())?;
    let response = post_idempotent_json(
        format!("{CORE_BASE_URL}/v1/materials/{material_id}/results"),
        &body,
        "material-result",
    )
    .await?;
    ensure_success(response, "활동 결과 저장 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn list_material_results(material_id: String) -> Result<serde_json::Value, String> {
    let response = client()?
        .get(format!(
            "{CORE_BASE_URL}/v1/materials/{material_id}/results"
        ))
        .send()
        .await
        .map_err(|error| error.to_string())?;
    ensure_success(response, "활동 결과 이력 조회 실패")
        .await?
        .json::<serde_json::Value>()
        .await
        .map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::MaterialResultRequest;
    use serde_json::json;

    #[test]
    fn optional_evidence_keeps_unknown_distinct_from_false() {
        let legacy = json!({"outcome":"completed", "observation":"관찰",
            "tags":[], "experience_axes":[]});
        let old: MaterialResultRequest = serde_json::from_value(legacy.clone()).unwrap();
        assert_eq!(old.evidence_checked, None);
        let mut with_evidence = legacy;
        with_evidence["book_id"] = json!("00000000-0000-0000-0000-000000000001");
        with_evidence["ai_hint"] = json!("힌트");
        with_evidence["evidence_checked"] = json!(false);
        with_evidence["child_reexplanation"] = json!("자기 설명");
        let parsed: MaterialResultRequest = serde_json::from_value(with_evidence).unwrap();
        let forwarded = serde_json::to_value(parsed).unwrap();
        assert_eq!(forwarded["evidence_checked"], false);
        assert_eq!(forwarded["ai_hint"], "힌트");
        assert_eq!(forwarded["child_reexplanation"], "자기 설명");
        assert_eq!(forwarded["book_id"], "00000000-0000-0000-0000-000000000001");
    }
}
