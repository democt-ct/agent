import base64
import json
import mimetypes
from typing import Optional
from urllib import error, request

from app.mcp.config import (
    DEFAULT_OPENAI_API_BASE,
    DEFAULT_OPENAI_MODEL,
    _get_setting,
    _get_setting_with_fallback,
    normalize_openai_api_key,
)


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _build_endpoint(api_base: str) -> str:
    return f"{api_base.rstrip('/')}/chat/completions"


def _guess_mime_type(filename: Optional[str], content_type: Optional[str]) -> str:
    if content_type:
        return content_type
    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    return "image/png"


def _extract_response_text(response_data) -> str:
    if not isinstance(response_data, dict):
        return ""

    choices = response_data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = _content_to_text(message.get("content", "")).strip()
        if content:
            return content

    for key in ("output_text", "text", "response", "content"):
        value = response_data.get(key)
        if value is None:
            continue
        content = _content_to_text(value).strip()
        if content:
            return content

    output = response_data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = _content_to_text(item.get("content", "")).strip()
            if content:
                return content

    return ""


def _build_payload(model_name: str, question: str, mime_type: str, image_base64: str):
    return {
        "model": model_name,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是患者智能辅助 Agent 的视觉分析模块。"
                    "请先客观提取图片中可见的信息，再围绕用户问题给出简洁中文摘要。"
                    "如果图片里有文字、表格、报告、药品包装、部位照片，请尽量描述清楚。"
                    "不要编造图片中看不见的信息。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"用户问题：{question}\n"
                            "请输出一段后续问答可直接使用的图片摘要。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}",
                        },
                    },
                ],
            },
        ],
    }


def analyze_image_with_llm(
    *,
    question: str,
    image_bytes: bytes,
    content_type: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    openai_api_base = _get_setting_with_fallback("VISION_API_BASE", "OPENAI_API_BASE", default=DEFAULT_OPENAI_API_BASE)
    openai_api_key = normalize_openai_api_key(
        _get_setting_with_fallback("VISION_API_KEY", "OPENAI_API_KEY", default=""),
        api_base=openai_api_base,
        allow_empty=True,
    )
    primary_model_name = _get_setting_with_fallback("VISION_MODEL", "OPENAI_VISION_MODEL", "OPENAI_MODEL", default=DEFAULT_OPENAI_MODEL)
    fallback_model_name = _get_setting_with_fallback("OPENAI_VISION_MODEL", "OPENAI_MODEL", default=DEFAULT_OPENAI_MODEL)

    mime_type = _guess_mime_type(filename, content_type)
    image_base64 = base64.b64encode(image_bytes).decode("ascii")

    model_candidates = [primary_model_name]
    if fallback_model_name and fallback_model_name not in model_candidates:
        model_candidates.append(fallback_model_name)

    last_error = None
    for model_name in model_candidates:
        payload = _build_payload(model_name, question, mime_type, image_base64)
        req = request.Request(
            _build_endpoint(openai_api_base),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=120) as resp:
                response_data = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            error_text = exc.read().decode("utf-8", errors="replace")
            last_error = f"图片分析调用失败: HTTP {exc.code}: {error_text}"
            continue
        except error.URLError as exc:
            last_error = f"图片分析调用失败: {exc.reason}"
            continue

        content = _extract_response_text(response_data)
        if content:
            return content

        if response_data.get("error"):
            last_error = f"图片分析模型返回错误: {response_data.get('error')}"
        else:
            response_preview = json.dumps(response_data, ensure_ascii=False)[:300]
            last_error = (
                f"图片分析模型 {model_name} 未返回可解析内容。"
                f" 返回片段: {response_preview}"
            )

    raise RuntimeError(last_error or "图片分析模型未返回有效结果。")
