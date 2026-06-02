CREATE TABLE IF NOT EXISTS batch_metadata (
  batch_id TEXT PRIMARY KEY,
  provider TEXT,
  enqueued_at TEXT,
  status TEXT,
  estimated_cost REAL,
  completed_at TEXT,
  raw_response JSON
);
CREATE INDEX IF NOT EXISTS idx_batch_metadata_status ON batch_metadata(status);

