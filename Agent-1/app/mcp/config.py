import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

try:
    # 优先从 app/config/（配置文件的正式归处）
    from app.config import local_settings
except ImportError:
    try:
        # 向后兼容：旧位置 app/mcp/local_settings.py（已弃用，仅为不破坏既有部署）
        from app.mcp import local_settings
    except ImportError:
        local_settings = None

from openai import OpenAI, APIError, APITimeoutError, RateLimitError


DEFAULT_OPENAI_API_BASE = "https://api-inference.modelscope.cn/v1/"
DEFAULT_OPENAI_MODEL = "deepseek-ai/DeepSeek-V3.2"

# Fallback model configuration (used when primary model fails)
DEFAULT_FALLBACK_API_BASE = "https://api-inference.modelscope.cn/v1/"
DEFAULT_FALLBACK_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"


def _get_setting_with_fallback(*names, default=None):
    for name in names:
        value = _get_setting(name, None)
        if value not in (None, ""):
            return value
    return default


def _is_local_api_base(api_base):
    if not api_base:
        return False
    normalized = str(api_base).strip().lower()
    return any(
        host in normalized
        for host in (
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "host.docker.internal",
            "192.168.",
            "10.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
        )
    )


def _get_local_setting(name, default=None):
    if local_settings is None:
        return default
    return getattr(local_settings, name, default)


def _get_setting(name, default=None):
    local_value = _get_local_setting(name, None)
    if local_value not in (None, ""):
        return local_value

    env_value = os.getenv(name)
    if env_value not in (None, ""):
        return env_value

    return default


@dataclass
class SimpleLLMResponse:
    content: str


def normalize_openai_api_key(raw_api_key, api_base=None, allow_empty=False):
    if not raw_api_key:
        if allow_empty or _is_local_api_base(api_base):
            return ""
        raise RuntimeError("OPENAI_API_KEY 环境变量未设置，请提供 ModelScope API Key")

    api_key = str(raw_api_key)
    # Clean up common copy-paste artifacts
    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
        "\u00a0": "",
        "\u3000": "",
    }
    for src, dst in replacements.items():
        api_key = api_key.replace(src, dst)

    api_key = "".join(ch for ch in api_key if ord(ch) >= 32 or ch == "\t")
    api_key = api_key.strip().strip('"').strip("'").strip()
    api_key = "".join(ch for ch in api_key if ord(ch) < 128)

    if not api_key and not (allow_empty or _is_local_api_base(api_base)):
        raise RuntimeError("OPENAI_API_KEY 环境变量未设置，请提供 ModelScope API Key")

    return api_key


def _log_retry(attempt: int, delay: float, reason: str):
    """Log an LLM retry attempt."""
    import logging
    logging.getLogger("app.mcp.config").warning(
        "LLM 调用重试 %d/%d (延迟 %.1fs): %s",
        attempt + 1, OpenAICompatChatClient.MAX_RETRIES, delay, reason,
    )


class OpenAICompatChatClient:
    """LLM client using the official OpenAI Python SDK with auto-retry and fallback."""

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(self, *, model, api_key, api_base, temperature=0,
                 fallback_model=None, fallback_api_base=None, fallback_api_key=None):
        self.model = model
        self.api_key = normalize_openai_api_key(api_key, api_base=api_base, allow_empty=True)
        self.api_base = str(api_base).rstrip("/")
        self.temperature = temperature
        self._fallback_model = fallback_model
        self._fallback_api_base = str(fallback_api_base).rstrip("/") if fallback_api_base else None
        self._fallback_api_key = fallback_api_key
        self._client = OpenAI(
            api_key=self.api_key if self.api_key else "not-needed",
            base_url=self.api_base,
            timeout=120.0,
            max_retries=0,  # we handle retries ourselves for better error messages
        )
        self._fallback_client = None

    def _get_fallback_client(self) -> Optional[OpenAI]:
        """Lazy-init the fallback client."""
        if self._fallback_client is None and self._fallback_model:
            key = self._fallback_api_key or self.api_key or "not-needed"
            base = self._fallback_api_base or self.api_base
            self._fallback_client = OpenAI(
                api_key=key,
                base_url=base,
                timeout=120.0,
                max_retries=0,
            )
        return self._fallback_client

    def invoke(self, prompt):
        # Try primary model with retries
        try:
            return self._invoke_with_retry(self._client, self.model, prompt)
        except RuntimeError as primary_error:
            # Try fallback if available
            fallback_client = self._get_fallback_client()
            if fallback_client:
                logger = logging.getLogger("app.mcp.config")
                logger.warning(
                    "主模型 %s 调用失败，切换到备用模型 %s: %s",
                    self.model, self._fallback_model, primary_error,
                )
                try:
                    return self._invoke_with_retry(
                        fallback_client, self._fallback_model, prompt
                    )
                except RuntimeError as fallback_error:
                    raise RuntimeError(
                        f"主模型和备用模型均调用失败。"
                        f"主模型({self.model}): {primary_error}. "
                        f"备用模型({self._fallback_model}): {fallback_error}"
                    ) from fallback_error
            raise

    def _invoke_with_retry(self, client: OpenAI, model: str, prompt: str) -> SimpleLLMResponse:
        """Invoke a model with retry logic."""
        payload = {
            "model": model,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat.completions.create(**payload)
                content = response.choices[0].message.content
                if not content or not content.strip():
                    raise RuntimeError(
                        f"模型 {model} 返回了空内容。"
                    )
                return SimpleLLMResponse(content=str(content).strip())

            except RateLimitError as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _log_retry(attempt, delay, f"RateLimitError: {exc.message}")
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"LLM 调用频率限制，已重试 {self.MAX_RETRIES} 次仍失败: {exc.message}"
                ) from exc

            except APITimeoutError as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _log_retry(attempt, delay, "APITimeoutError")
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"LLM 调用超时，已重试 {self.MAX_RETRIES} 次仍失败"
                ) from exc

            except APIError as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES - 1 and exc.status_code and exc.status_code >= 500:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    _log_retry(attempt, delay, f"APIError HTTP {exc.status_code}: {exc.message}")
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"LLM 调用失败 (HTTP {exc.status_code}): {exc.message}"
                ) from exc

        raise RuntimeError(
            f"LLM 调用在 {self.MAX_RETRIES} 次重试后全部失败: {last_error}"
        ) from last_error


def configure_llm_environment(api_key=None, api_base=DEFAULT_OPENAI_API_BASE):
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    os.environ.setdefault("OPENAI_API_BASE", api_base)


def get_llm():
    openai_api_base = _get_setting_with_fallback("TEXT_API_BASE", "OPENAI_API_BASE", default=DEFAULT_OPENAI_API_BASE)
    openai_api_key = normalize_openai_api_key(
        _get_setting_with_fallback("TEXT_API_KEY", "OPENAI_API_KEY", default=""),
        api_base=openai_api_base,
        allow_empty=True,
    )
    model_name = _get_setting_with_fallback("TEXT_MODEL", "OPENAI_MODEL", default=DEFAULT_OPENAI_MODEL)

    # Fallback model configuration
    fallback_model = _get_setting_with_fallback(
        "TEXT_FALLBACK_MODEL", "OPENAI_FALLBACK_MODEL",
        default=DEFAULT_FALLBACK_MODEL,
    )
    fallback_api_base = _get_setting_with_fallback(
        "TEXT_FALLBACK_API_BASE", "OPENAI_FALLBACK_API_BASE",
        default=DEFAULT_FALLBACK_API_BASE,
    )
    fallback_api_key = _get_setting_with_fallback(
        "TEXT_FALLBACK_API_KEY", "OPENAI_FALLBACK_API_KEY",
        default=openai_api_key,
    )

    return OpenAICompatChatClient(
        model=model_name,
        api_key=openai_api_key,
        api_base=openai_api_base,
        temperature=0,
        fallback_model=fallback_model,
        fallback_api_base=fallback_api_base,
        fallback_api_key=fallback_api_key,
    )
