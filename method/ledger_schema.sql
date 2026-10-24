PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assets (
 asset_id TEXT PRIMARY KEY, pack_number INTEGER NOT NULL CHECK(pack_number BETWEEN 1 AND 10),
 ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 200), category_id TEXT NOT NULL,
 name_en TEXT NOT NULL, request_sha256 TEXT NOT NULL UNIQUE, args_json TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'planned', accepted INTEGER NOT NULL DEFAULT 0 CHECK(accepted IN (0,1)),
 local_file TEXT, visible_sha256 TEXT, qa_json TEXT,
 UNIQUE(pack_number,ordinal)
);
CREATE TABLE IF NOT EXISTS attempts (
 attempt_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL UNIQUE REFERENCES assets(asset_id),
 request_id TEXT NOT NULL UNIQUE, request_sha256 TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('prepared','submitting','submitted','ambiguous','completed','failed','refunded')),
 reserved_units INTEGER NOT NULL DEFAULT 1 CHECK(reserved_units=1),
 submitted_at TEXT, job_id TEXT UNIQUE, gallery_id TEXT, receipt_path TEXT,
 charged_units INTEGER CHECK(charged_units IS NULL OR charged_units>=0), notes TEXT
);
CREATE TABLE IF NOT EXISTS budget_reservations (
 attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
 units INTEGER NOT NULL DEFAULT 1 CHECK(units=1),
 state TEXT NOT NULL DEFAULT 'held' CHECK(state IN ('held','settled','released')),
 release_evidence TEXT,
 CHECK(state<>'released' OR release_evidence IS NOT NULL)
);
CREATE TRIGGER IF NOT EXISTS enforce_budget_before_reserve
BEFORE INSERT ON budget_reservations
WHEN (SELECT COALESCE(SUM(units),0) FROM budget_reservations WHERE state<>'released')+NEW.units>2000
BEGIN SELECT RAISE(ABORT,'Hard budget limit: 2000 reserved or settled units'); END;
CREATE TRIGGER IF NOT EXISTS enforce_submission_count
BEFORE INSERT ON attempts
WHEN (SELECT COUNT(*) FROM attempts)>=2000
BEGIN SELECT RAISE(ABORT,'Hard attempt limit: 2000'); END;
CREATE TABLE IF NOT EXISTS events (
 event_id INTEGER PRIMARY KEY, asset_id TEXT, event_time TEXT NOT NULL,
 event_type TEXT NOT NULL, detail_json TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS budget_summary AS
SELECT (SELECT COUNT(*) FROM attempts) AS attempts,
 (SELECT COALESCE(SUM(charged_units),0) FROM attempts) AS confirmed_charged,
 (SELECT COALESCE(SUM(units),0) FROM budget_reservations WHERE state='held') AS held,
 (SELECT COALESCE(SUM(units),0) FROM budget_reservations WHERE state<>'released') AS occupied,
 (SELECT COUNT(*) FROM attempts WHERE state='ambiguous') AS ambiguous,
 (SELECT COUNT(*) FROM assets WHERE accepted=1) AS accepted;
