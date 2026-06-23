CREATE TABLE IF NOT EXISTS user_preferences (
  id TEXT PRIMARY KEY,
  owner_type TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  preferred_pace TEXT,
  interests_json TEXT,
  distance_tolerance TEXT,
  source TEXT NOT NULL DEFAULT 'conversation',
  confidence REAL NOT NULL DEFAULT 0.7,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_preferences_owner
  ON user_preferences(owner_type, owner_id);
