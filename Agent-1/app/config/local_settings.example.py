# ════════════════════════════════════════════════════════════════════
# 本地配置示例 (app/config/local_settings.example.py)
#
# 用法：
#   1. 复制本文件为 app/config/local_settings.py
#   2. 修改其中的 API Key、数据库连接等敏感值
#   3. local_settings.py 已被 .gitignore 忽略，不会提交（含密钥）
#
# 配置优先级（app/mcp/config.py:_get_setting）：
#   app/config/local_settings.py  >  环境变量  >  代码默认值
#
# 旧路径 app/mcp/local_settings.py 仍被向后兼容支持，但已弃用。
# ════════════════════════════════════════════════════════════════════

# Text generation can use a local Ollama OpenAI-compatible endpoint.
TEXT_API_KEY = "ollama"
TEXT_API_BASE = "http://127.0.0.1:11434/v1/"
TEXT_MODEL = "qwen:7b"

# Keep image analysis on a remote OpenAI-compatible vision API.
VISION_API_KEY = "replace-with-your-vision-key"
VISION_API_BASE = "https://api-inference.modelscope.cn/v1/"
VISION_MODEL = "Qwen/Qwen3.5-397B-A17B"

# Backward-compatible defaults.
OPENAI_API_KEY = VISION_API_KEY
OPENAI_API_BASE = VISION_API_BASE
OPENAI_MODEL = TEXT_MODEL
OPENAI_VISION_MODEL = VISION_MODEL

# Knowledge embedding backend:
# - Use KNOWLEDGE_EMBEDDING_PROVIDER="sentence_transformers" for local Chinese embeddings.
# - Use KNOWLEDGE_EMBEDDING_PROVIDER="openai" with a dedicated embedding endpoint.
# KNOWLEDGE_EMBEDDING_PROVIDER = "sentence_transformers"
# KNOWLEDGE_HF_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
# KNOWLEDGE_EMBEDDING_PROVIDER = "openai"
# KNOWLEDGE_EMBEDDING_API_BASE = "https://your-embeddings-endpoint/v1/"
# KNOWLEDGE_EMBEDDING_API_KEY = "replace-with-your-embedding-key"
# KNOWLEDGE_EMBEDDING_MODEL = "text-embedding-3-small"

# Optional TTS settings:
# TTS_PROVIDER = "kokoro"

# PostgreSQL configuration (production database)
PG_HOST = "localhost"
PG_PORT = "5432"
PG_USER = "postgres"
PG_PASSWORD = "postgres"
PG_DATABASE = "patient_agent"

# Redis configuration (session cache)
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = None
# Or use REDIS_URL format:
# REDIS_URL = "redis://localhost:6379/0"

# Session cache TTL (in seconds) - 24 hours by default
SESSION_CACHE_TTL = 86400
