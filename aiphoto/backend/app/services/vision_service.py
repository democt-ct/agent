import base64
import httpx
from typing import Optional
from app.core.config import settings


class VisionService:
    def __init__(self):
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        self.api_token = settings.MODELSCOPE_API_TOKEN

    async def analyze_image(self, image_path: str, prompt: str = "请详细描述这张图片的内容、光线、构图和色彩") -> str:
        """Use Qwen-VL vision model to analyze an image and return a natural language description."""
        if not self.api_token:
            return self._fallback_analysis(image_path)

        # Read image and encode as base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        ext = image_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
        data_url = f"data:image/{mime};base64,{image_b64}"

        body = {
            "model": "qwen-vl-plus",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": data_url},
                            {"text": prompt},
                        ]
                    }
                ]
            },
            "parameters": {"max_tokens": 600},
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.api_url,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    output = data.get("output", {})
                    choices = output.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
                        return content or "图片分析完成，但模型未返回描述。"
                # Fallback on API error
                return self._fallback_analysis(image_path)
        except Exception:
            return self._fallback_analysis(image_path)

    async def chat(self, message: str, image_path: Optional[str] = None) -> str:
        """Chat with Qwen-VL about an image or general photo editing advice."""
        if not self.api_token:
            return self._simple_reply(message, image_path)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个专业的智能修图助手，名为「AI Photo Agent」。"
                    "你可以仔细观察图片的内容、光线、构图、色彩，并根据用户需求提供针对该图片的个性化修图参数。"
                    "回复时请使用中文，语言友好专业。"
                ),
            },
        ]

        if image_path:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
            data_url = f"data:image/{mime};base64,{image_b64}"

            messages.append({
                "role": "user",
                "content": [
                    {"image": data_url},
                    {"text": message},
                ],
            })
        else:
            messages.append({"role": "user", "content": [{"text": message}]})

        body = {
            "model": "qwen-vl-plus",
            "input": {"messages": messages},
            "parameters": {"max_tokens": 600},
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.api_url,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("output", {}).get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if isinstance(content, list):
                            content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
                        return content or "收到！"
                return self._simple_reply(message, image_path)
        except Exception:
            return self._simple_reply(message, image_path)

    def _fallback_analysis(self, image_path: str) -> str:
        """Fallback: basic OpenCV analysis when API is unavailable."""
        import cv2, numpy as np
        img = cv2.imread(image_path)
        if img is None:
            return "无法读取图片，请确认文件格式正确。"
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        contrast = np.std(gray)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1])

        b_label = "偏暗" if brightness < 85 else ("偏亮" if brightness > 170 else "正常")
        c_label = "偏低" if contrast < 30 else "正常"
        q_label = "模糊" if laplacian < 100 else ("清晰" if laplacian > 1000 else "一般")
        s_label = "偏低" if saturation < 50 else "正常"

        return (
            f"图片分析结果（离线模式）：\n"
            f"亮度：{b_label}（{brightness:.0f}），对比度：{c_label}（{contrast:.0f}）\n"
            f"清晰度：{q_label}（{laplacian:.0f}），饱和度：{s_label}（{saturation:.0f}）"
        )

    def _simple_reply(self, message: str, image_path: Optional[str] = None) -> str:
        """Simple keyword-based reply when API is unavailable. Returns marker strings for chat endpoint to process."""
        msg = message.lower()

        # Style keywords — match against all STYLE_PRESETS
        extra_aliases = {
            "cinematic": "cinematic", "电影": "cinematic",
            "vintage": "vintage", "复古": "vintage",
            "bright": "bright", "明亮": "bright",
            "moody": "moody", "暗调": "moody", "情绪": "moody",
            "fuji": "fuji", "富士": "fuji", "胶片": "fuji",
            "leica": "leica", "徕卡": "leica",
            "hongkong": "hongkong", "港风": "hongkong", "香港": "hongkong",
            "japanese": "japanese", "日系": "japanese", "清新": "japanese",
            "instagram": "instagram", "ins": "instagram",
            "xiaohongshu": "xiaohongshu", "小红书": "xiaohongshu",
            "blackgold": "blackgold", "黑金": "blackgold",
            "morandi": "morandi", "莫兰迪": "morandi",
            "cyberpunk": "cyberpunk", "赛博": "cyberpunk", "朋克": "cyberpunk",
        }
        # Sort by length descending for best match
        sorted_kw = sorted(extra_aliases.items(), key=lambda x: -len(x[0]))
        for kw, style in sorted_kw:
            if kw in msg:
                return f"[STYLE:{style}]"

        # Edit keywords → auto enhance
        if any(kw in msg for kw in ["优化", "增强", "美化", "修", "调", "auto", "enhance"]):
            return "[AUTO_ENHANCE]"

        # Analyze
        if any(kw in msg for kw in ["分析", "看看", "describe", "analyze", "描述", "怎么样"]):
            if image_path:
                return self._fallback_analysis(image_path)
            return "请上传一张图片，我可以帮你分析。"

        # Default
        if image_path:
            return self._fallback_analysis(image_path)
        return "请上传一张图片，或者告诉我你想怎么修图～"
