-- 002: User style presets
-- Allows users to save custom style presets (DB-backed, optional enhancement over JSON file storage)

CREATE TABLE IF NOT EXISTS user_style_presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    brightness FLOAT DEFAULT 0,
    contrast FLOAT DEFAULT 0,
    saturation FLOAT DEFAULT 0,
    temperature FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_style_presets_user_id ON user_style_presets(user_id);
