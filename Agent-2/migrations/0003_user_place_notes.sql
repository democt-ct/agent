CREATE TABLE IF NOT EXISTS user_place_notes (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  city TEXT,
  query TEXT NOT NULL,
  place_name TEXT,
  rating REAL,
  comment TEXT,
  poi_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_user_place_notes_session_id
  ON user_place_notes(session_id);

CREATE INDEX IF NOT EXISTS idx_user_place_notes_city
  ON user_place_notes(city);
