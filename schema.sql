-- D1 schema for optional sign-in + sync, reconstructed from the queries in worker/worker.js.
-- Apply with: npx wrangler d1 execute stopline --remote --file=schema.sql
CREATE TABLE IF NOT EXISTS users (
  sub        TEXT PRIMARY KEY,   -- Google account subject id
  email      TEXT NOT NULL,
  data       TEXT,               -- JSON blob of synced calculator/journal state (max 256 KB)
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  sub        TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_sub ON sessions(sub);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
