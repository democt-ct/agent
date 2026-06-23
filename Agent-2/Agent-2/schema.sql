CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  visitor_id TEXT,
  title TEXT NOT NULL DEFAULT '新的旅行规划',
  status TEXT NOT NULL DEFAULT 'active',
  source TEXT NOT NULL DEFAULT 'web',
  current_requirement_version INTEGER NOT NULL DEFAULT 0,
  current_itinerary_version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_visitor_id ON sessions(visitor_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS trip_requirements (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  raw_input TEXT NOT NULL,
  origin_city TEXT,
  destination TEXT,
  start_date TEXT,
  end_date TEXT,
  trip_days INTEGER,
  budget_min INTEGER,
  budget_max INTEGER,
  travelers_summary TEXT,
  interests_json TEXT,
  constraints_json TEXT,
  structured_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_requirements_session_version
  ON trip_requirements(session_id, version);
CREATE INDEX IF NOT EXISTS idx_trip_requirements_destination
  ON trip_requirements(destination);
CREATE INDEX IF NOT EXISTS idx_trip_requirements_start_date
  ON trip_requirements(start_date);

CREATE TABLE IF NOT EXISTS itinerary_drafts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  summary TEXT,
  itinerary_json TEXT NOT NULL,
  budget_estimate_json TEXT,
  warnings_json TEXT,
  generator_type TEXT NOT NULL DEFAULT 'template',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id),
  FOREIGN KEY (requirement_id) REFERENCES trip_requirements(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_itinerary_drafts_session_version
  ON itinerary_drafts(session_id, version);
CREATE INDEX IF NOT EXISTS idx_itinerary_drafts_requirement_id
  ON itinerary_drafts(requirement_id);
CREATE INDEX IF NOT EXISTS idx_itinerary_drafts_status
  ON itinerary_drafts(status);

CREATE TABLE IF NOT EXISTS conversation_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  message_type TEXT NOT NULL DEFAULT 'text',
  content TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session_id
  ON conversation_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at
  ON conversation_messages(created_at);

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
