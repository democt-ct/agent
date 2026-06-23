import io
import importlib.util
import json
import os
from pathlib import Path
from typing import Optional, Tuple
from urllib import error, request

from app.mcp.config import DEFAULT_OPENAI_API_BASE, _get_setting, normalize_openai_api_key


DEFAULT_TTS_VOICE = "alloy"
DEFAULT_TTS_FORMAT = "mp3"
DEFAULT_KOKORO_REPO_ID = "hexgrad/Kokoro-82M-v1.1-zh"
DEFAULT_KOKORO_VOICE = "zf_001"


class SpeechSynthesisError(RuntimeError):
    def __init__(self, message: str, *, provider: str, status_code: int = 503, retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


def _looks_like_network_error(message: str) -> bool:
    normalized = (message or "").lower()
    indicators = (
        "winerror",
        "connection",
        "timeout",
        "timed out",
        "maxretryerror",
        "failed to establish a new connection",
        "actively refused",
        "refused",
        "network",
        "huggingface.co",
    )
    return any(item in normalized for item in indicators)


def _kokoro_is_available() -> bool:
    return all(importlib.util.find_spec(module_name) is not None for module_name in ("kokoro", "numpy", "soundfile"))


def _normalize_format(response_format: Optional[str]) -> str:
    fmt = (response_format or DEFAULT_TTS_FORMAT).strip().lower()
    return fmt or DEFAULT_TTS_FORMAT


def _kokoro_assets_ready(repo_id: str) -> bool:
    normalized_repo = (repo_id or "").strip()
    if not normalized_repo:
        return False

    required_files = ("config.json", "kokoro-v1_1-zh.pth")
    local_path = Path(normalized_repo)
    if local_path.is_dir():
        return all((local_path / filename).exists() for filename in required_files)

    repo_cache_name = "models--" + normalized_repo.replace("/", "--")
    cache_roots = []

    hf_home = os.getenv("HF_HOME")
    if hf_home:
        cache_roots.append(Path(hf_home) / "hub")

    xdg_cache_home = os.getenv("XDG_CACHE_HOME")
    if xdg_cache_home:
        cache_roots.append(Path(xdg_cache_home) / "huggingface" / "hub")

    userprofile = os.getenv("USERPROFILE")
    if userprofile:
        cache_roots.append(Path(userprofile) / ".cache" / "huggingface" / "hub")

    appdata_local = os.getenv("LOCALAPPDATA")
    if appdata_local:
        cache_roots.append(Path(appdata_local) / "huggingface" / "hub")

    cache_roots.append(Path.home() / ".cache" / "huggingface" / "hub")

    for cache_root in cache_roots:
        snapshot_root = cache_root / repo_cache_name / "snapshots"
        if not snapshot_root.exists():
            continue
        snapshot_dirs = [path for path in snapshot_root.iterdir() if path.is_dir()]
        if any(all((snapshot_dir / filename).exists() for filename in required_files) for snapshot_dir in snapshot_dirs):
            return True
    return False


def _synthesize_with_openai_compat(
    *,
    text: str,
    voice: Optional[str] = None,
    response_format: str = DEFAULT_TTS_FORMAT,
) -> Tuple[bytes, str, str, str, str]:
    provider_name = "openai_compat"
    openai_api_base = _get_setting("OPENAI_API_BASE", DEFAULT_OPENAI_API_BASE).rstrip("/")
    openai_api_key = normalize_openai_api_key(_get_setting("OPENAI_API_KEY"), api_base=openai_api_base, allow_empty=True)
    model_name = (_get_setting("OPENAI_TTS_MODEL") or "").strip()
    if not model_name:
        raise SpeechSynthesisError(
            "OPENAI_TTS_MODEL is not configured.",
            provider=provider_name,
            status_code=500,
        )

    selected_voice = (voice or _get_setting("OPENAI_TTS_VOICE") or DEFAULT_TTS_VOICE).strip()
    selected_format = _normalize_format(response_format)
    payload = {
        "model": model_name,
        "input": text,
        "voice": selected_voice,
        "response_format": selected_format,
    }

    headers = {
        "Content-Type": "application/json",
    }
    if openai_api_key:
        headers["Authorization"] = f"Bearer {openai_api_key}"

    req = request.Request(
        f"{openai_api_base}/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=180) as resp:
            audio_bytes = resp.read()
            mime_type = resp.headers.get_content_type() or f"audio/{selected_format}"
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise SpeechSynthesisError(
            f"TTS request failed: HTTP {exc.code}: {error_text}",
            provider=provider_name,
            status_code=502,
            retryable=exc.code >= 500,
        ) from exc
    except error.URLError as exc:
        raise SpeechSynthesisError(
            f"TTS request failed: {exc.reason}",
            provider=provider_name,
            status_code=503,
            retryable=True,
        ) from exc

    if not audio_bytes:
        raise SpeechSynthesisError(
            "TTS request failed: empty audio response.",
            provider=provider_name,
            status_code=502,
        )

    return audio_bytes, mime_type, selected_voice, model_name, selected_format


def _synthesize_with_kokoro(
    *,
    text: str,
    voice: Optional[str] = None,
    response_format: str = DEFAULT_TTS_FORMAT,
) -> Tuple[bytes, str, str, str, str]:
    provider_name = "kokoro"
    repo_id = (_get_setting("KOKORO_REPO_ID") or DEFAULT_KOKORO_REPO_ID).strip()
    selected_voice = (voice or _get_setting("KOKORO_VOICE") or DEFAULT_KOKORO_VOICE).strip()
    if not _kokoro_assets_ready(repo_id):
        raise SpeechSynthesisError(
            f"Kokoro model assets are not ready: {repo_id}.",
            provider=provider_name,
            status_code=503,
            retryable=False,
        )

    try:
        import numpy as np
    except ImportError as exc:
        raise SpeechSynthesisError(
            "Kokoro dependency missing: numpy.",
            provider=provider_name,
            status_code=500,
        ) from exc

    try:
        import soundfile as sf
    except ImportError as exc:
        raise SpeechSynthesisError(
            "Kokoro dependency missing: soundfile.",
            provider=provider_name,
            status_code=500,
        ) from exc

    try:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from kokoro import KPipeline
    except ImportError as exc:
        raise SpeechSynthesisError(
            'Kokoro is not installed. Run: python -m pip install kokoro "misaki[zh]" soundfile',
            provider=provider_name,
            status_code=500,
        ) from exc

    try:
        pipeline = KPipeline(lang_code="z", repo_id=repo_id)
        generator = pipeline(text, voice=selected_voice)

        audio_segments = []
        for _, _, audio_piece in generator:
            if audio_piece is None:
                continue
            audio_segments.append(np.asarray(audio_piece))

        if not audio_segments:
            raise SpeechSynthesisError(
                "Kokoro returned no audio segments.",
                provider=provider_name,
                status_code=502,
            )

        audio = np.concatenate(audio_segments)
        buffer = io.BytesIO()
        sf.write(buffer, audio, 24000, format="WAV")
        audio_bytes = buffer.getvalue()
        if not audio_bytes:
            raise SpeechSynthesisError(
                "Kokoro audio encoding returned empty output.",
                provider=provider_name,
                status_code=502,
            )
    except SpeechSynthesisError:
        raise
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        retryable = _looks_like_network_error(message)
        raise SpeechSynthesisError(
            f"Kokoro synthesis failed: {message}",
            provider=provider_name,
            status_code=503 if retryable else 500,
            retryable=retryable,
        ) from exc

    actual_format = "wav"
    return audio_bytes, "audio/wav", selected_voice, repo_id, actual_format


def synthesize_speech_with_llm(
    *,
    text: str,
    voice: Optional[str] = None,
    response_format: str = DEFAULT_TTS_FORMAT,
) -> Tuple[bytes, str, str, str, str]:
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise SpeechSynthesisError(
            "Speech text must not be empty.",
            provider="unknown",
            status_code=400,
        )

    provider_setting = (_get_setting("TTS_PROVIDER") or "").strip().lower()
    provider = provider_setting or ("kokoro" if _kokoro_is_available() else "openai_compat")

    if provider == "kokoro":
        return _synthesize_with_kokoro(
            text=cleaned_text,
            voice=voice,
            response_format=response_format,
        )

    if provider == "openai_compat":
        try:
            return _synthesize_with_openai_compat(
                text=cleaned_text,
                voice=voice,
                response_format=response_format,
            )
        except SpeechSynthesisError:
            if not _kokoro_is_available():
                raise
            return _synthesize_with_kokoro(
                text=cleaned_text,
                voice=voice,
                response_format=response_format,
            )

    raise SpeechSynthesisError(
        f"Unknown TTS_PROVIDER: {provider}",
        provider=provider or "unknown",
        status_code=500,
    )
