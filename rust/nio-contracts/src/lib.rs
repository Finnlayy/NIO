use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const CONTRACT_VERSION: &str = "1.0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Triage,
    Backlog,
    Ready,
    InProgress,
    Blocked,
    Completed,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkerStatus {
    Idle,
    Busy,
    Disabled,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KanbanTask {
    pub id: String,
    pub board_id: String,
    pub title: String,
    pub description: String,
    pub status: TaskStatus,
    pub priority: i64,
    pub assigned_worker_uid: Option<String>,
    pub parent_id: Option<String>,
    pub dependencies: Vec<String>,
    pub required_skills: Vec<String>,
    pub is_rollup: bool,
    pub attempts: i64,
    pub result_payload: Option<serde_json::Map<String, Value>>,
    pub block_reason: String,
    pub workspace_repo: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub started_at: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Worker {
    pub uid: String,
    pub name: String,
    pub skills: Vec<String>,
    pub soul_md: String,
    pub status: WorkerStatus,
    pub fail_count: i64,
    pub breaker_open_until: Option<String>,
    pub updated_at: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Experience {
    pub id: String,
    pub worker_uid: String,
    pub task_id: String,
    pub summary: String,
    pub lessons: Vec<String>,
    pub skills_delta: Vec<String>,
    pub outcome: String,
    pub vault_synced: bool,
    pub created_at: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AuditEntry {
    pub seq: i64,
    pub ts: String,
    pub actor: String,
    pub action: String,
    pub category: String,
    pub subject: String,
    pub payload: serde_json::Map<String, Value>,
    pub prev_hash: String,
    pub entry_hash: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KanbanEvent {
    pub kind: String,
    pub task_id: Option<String>,
    pub board_id: Option<String>,
    pub status: Option<String>,
    pub worker_uid: Option<String>,
    pub payload: serde_json::Map<String, Value>,
    pub ts: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ToolCall {
    pub tool: String,
    pub arguments: serde_json::Map<String, Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RustLimb {
    pub name: String,
    pub version: String,
    pub contract_version: String,
    pub endpoint: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RustLimbRequest {
    pub request_id: String,
    pub operation: String,
    pub params: serde_json::Map<String, Value>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RustLimbResponse {
    pub request_id: String,
    pub ok: bool,
    pub result: Option<serde_json::Map<String, Value>>,
    pub error: Option<String>,
}
