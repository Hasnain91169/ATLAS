SCHEMA_VERSION = 11

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS system_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_brief (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    date TEXT NOT NULL,
    markdown TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS board_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    week_start_date TEXT NOT NULL,
    raw_markdown TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    context_type TEXT NOT NULL,
    context_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    message_markdown TEXT NOT NULL,
    status TEXT NOT NULL,
    tags TEXT NOT NULL,
    json_payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hourly_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    date TEXT NOT NULL,
    raw_markdown TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    raw_markdown TEXT NOT NULL,
    json_payload TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acknowledgements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_list (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_item (
    id TEXT PRIMARY KEY,
    list_id TEXT NOT NULL,
    title TEXT NOT NULL,
    notes TEXT,
    due TEXT,
    status TEXT NOT NULL,
    updated TEXT,
    completed TEXT,
    parent TEXT,
    position TEXT,
    raw_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    list_count INTEGER NOT NULL,
    task_count INTEGER NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_action (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    action_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_at TEXT,
    executed_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS audience_forecast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    requirement TEXT NOT NULL,
    verdict TEXT NOT NULL,
    risk_score REAL NOT NULL,
    report_markdown TEXT NOT NULL,
    simulation_id TEXT,
    report_id TEXT,
    raw_json TEXT NOT NULL
);
"""
