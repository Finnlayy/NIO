use nio_contracts::*;
use serde::de::DeserializeOwned;
use serde::Serialize;
use std::fs;
use std::path::PathBuf;

fn test_fixture<T>(filename: &str)
where
    T: DeserializeOwned + Serialize + std::fmt::Debug + PartialEq,
{
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("../../tests/fixtures/kanban");
    path.push(filename);

    let content = fs::read_to_string(&path).expect(&format!("Failed to read {}", filename));
    let original: serde_json::Value =
        serde_json::from_str(&content).expect(&format!("Invalid JSON in {}", filename));

    let parsed: T =
        serde_json::from_value(original.clone()).expect(&format!("Failed to deserialize {}", filename));

    let reserialized = serde_json::to_value(&parsed).expect("Failed to serialize");
    assert_eq!(original, reserialized, "Mismatch in {}", filename);
}

#[test]
fn test_kanban_task() {
    test_fixture::<KanbanTask>("task_minimal.json");
    test_fixture::<KanbanTask>("task_full.json");
}

#[test]
fn test_worker() {
    test_fixture::<Worker>("worker_minimal.json");
    test_fixture::<Worker>("worker_full.json");
}

#[test]
fn test_experience() {
    test_fixture::<Experience>("experience_minimal.json");
    test_fixture::<Experience>("experience_full.json");
}

#[test]
fn test_audit_entry() {
    test_fixture::<AuditEntry>("audit_entry_minimal.json");
    test_fixture::<AuditEntry>("audit_entry_full.json");
}

#[test]
fn test_kanban_event() {
    test_fixture::<KanbanEvent>("event_minimal.json");
    test_fixture::<KanbanEvent>("event_full.json");
}

#[test]
fn test_tool_call() {
    test_fixture::<ToolCall>("tool_call_minimal.json");
    test_fixture::<ToolCall>("tool_call_full.json");
}

#[test]
fn test_rust_limb() {
    test_fixture::<RustLimb>("rust_limb_minimal.json");
    test_fixture::<RustLimb>("rust_limb_full.json");
}

#[test]
fn test_rust_limb_request() {
    test_fixture::<RustLimbRequest>("rust_limb_request_minimal.json");
    test_fixture::<RustLimbRequest>("rust_limb_request_full.json");
}

#[test]
fn test_rust_limb_response() {
    test_fixture::<RustLimbResponse>("rust_limb_response_minimal.json");
    test_fixture::<RustLimbResponse>("rust_limb_response_full.json");
}

#[test]
fn test_deny_unknown_fields() {
    let bad_json = r#"{
        "id": "t-1",
        "board_id": "b-1",
        "title": "Min",
        "description": "",
        "status": "triage",
        "priority": 0,
        "assigned_worker_uid": null,
        "parent_id": null,
        "dependencies": [],
        "required_skills": [],
        "is_rollup": false,
        "attempts": 0,
        "result_payload": null,
        "block_reason": "",
        "workspace_repo": null,
        "created_at": "2023-10-29T16:13:00Z",
        "updated_at": "2023-10-29T16:13:00Z",
        "started_at": null,
        "extra_field": 42
    }"#;

    let res: Result<KanbanTask, _> = serde_json::from_str(bad_json);
    assert!(res.is_err(), "Expected deserialization to fail due to unknown field");
}
