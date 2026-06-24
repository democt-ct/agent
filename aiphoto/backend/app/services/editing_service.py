import cv2
import numpy as np
from typing import Dict, Optional, List
from app.services.image_service import ImageService
from app.services.analysis_service import AnalysisService

# ============================================================
# Style Presets — 13 styles × 12 parameters
# ============================================================
STYLE_PRESETS: Dict[str, dict] = {
    # ── 基础 ──────────────────────────────────────────────
    "bright": {
        "label_zh": "明亮风",
        "description": "提升亮度与饱和度，清新通透，适合小清新照片",
        "brightness": 0.3, "contrast": 0, "saturation": 20, "temperature": 0,
        "sharpness": 0, "highlights": 0, "shadows": 10,
        "vignette": 0, "grain": 0, "tint": 0, "fade": 0, "hue_shift": 0,
        "category": "基础",
    },
    # ── 氛围 ──────────────────────────────────────────────
    "cinematic": {
        "label_zh": "电影感",
        "description": "暗部下沉，冷色调，暗角，营造电影氛围",
        "brightness": -0.2, "contrast": 30, "saturation": 0, "temperature": -20,
        "sharpness": 5, "highlights": -15, "shadows": -10,
        "vignette": 35, "grain": 8, "tint": 0, "fade": 0, "hue_shift": 0,
        "category": "氛围",
    },
    "moody": {
        "label_zh": "情绪风",
        "description": "大幅降亮度，高对比，冷色调，深沉情绪感",
        "brightness": -0.3, "contrast": 40, "saturation": 0, "temperature": -25,
        "sharpness": 0, "highlights": -20, "shadows": -15,
        "vignette": 40, "grain": 0, "tint": 0, "fade": 10, "hue_shift": 0,
        "category": "氛围",
    },
    "blackgold": {
        "label_zh": "黑金风",
        "description": "除金/橙色外去色，高对比，暗角，适合夜景城市",
        "brightness": -0.2, "contrast": 45, "saturation": -80, "temperature": 15,
        "sharpness": 15, "highlights": 10, "shadows": -20,
        "vignette": 25, "grain": 0, "tint": 0, "fade": 0, "hue_shift": 0,
        "category": "氛围",
    },
    "cyberpunk": {
        "label_zh": "赛博朋克",
        "description": "高对比冷色调，蓝紫霓虹感，强暗角，未来科技风",
        "brightness": -0.15, "contrast": 40, "saturation": 30, "temperature": -30,
        "sharpness": 20, "highlights": 10, "shadows": -10,
        "vignette": 50, "grain": 5, "tint": 15, "fade": 0, "hue_shift": 0,
        "category": "氛围",
    },
    # ── 胶片 ──────────────────────────────────────────────
    "fuji": {
        "label_zh": "富士胶片",
        "description": "微暖调，低对比，淡雅青绿，柔和颗粒感",
        "brightness": 0.05, "contrast": -5, "saturation": 10, "temperature": 8,
        "sharpness": -5, "highlights": -10, "shadows": 15,
        "vignette": 10, "grain": 12, "tint": -5, "fade": 15, "hue_shift": 0,
        "category": "胶片",
    },
    "leica": {
        "label_zh": "徕卡风",
        "description": "高对比度，浓郁色彩，暗角，锐利质感",
        "brightness": -0.1, "contrast": 35, "saturation": 15, "temperature": -5,
        "sharpness": 25, "highlights": -10, "shadows": -5,
        "vignette": 20, "grain": 6, "tint": 0, "fade": 0, "hue_shift": 0,
        "category": "胶片",
    },
    "vintage": {
        "label_zh": "复古风",
        "description": "暖黄调，降饱和度，柔和对比，褪色做旧，颗粒感",
        "brightness": 0.0, "contrast": -10, "saturation": -30, "temperature": 15,
        "sharpness": -10, "highlights": -5, "shadows": 10,
        "vignette": 30, "grain": 20, "tint": 0, "fade": 25, "hue_shift": 0,
        "category": "胶片",
    },
    # ── 地域 ──────────────────────────────────────────────
    "hongkong": {
        "label_zh": "港风",
        "description": "90年代香港电影：暖黄调，高饱和，绿影暗角，柔光",
        "brightness": -0.1, "contrast": 20, "saturation": 25, "temperature": 20,
        "sharpness": -5, "highlights": -5, "shadows": 5,
        "vignette": 15, "grain": 10, "tint": -8, "fade": 10, "hue_shift": 0,
        "category": "地域",
    },
    "japanese": {
        "label_zh": "日系清新",
        "description": "过曝感，低对比，偏青蓝，褪色，柔焦，淡雅通透",
        "brightness": 0.3, "contrast": -15, "saturation": -5, "temperature": -10,
        "sharpness": -15, "highlights": 15, "shadows": 20,
        "vignette": 0, "grain": 0, "tint": -5, "fade": 20, "hue_shift": 0,
        "category": "地域",
    },
    # ── 社交 ──────────────────────────────────────────────
    "instagram": {
        "label_zh": "INS风",
        "description": "暖色调，略增对比与饱和，轻微褪色，高级社交感",
        "brightness": 0.05, "contrast": 15, "saturation": 12, "temperature": 10,
        "sharpness": 10, "highlights": -5, "shadows": 5,
        "vignette": 8, "grain": 0, "tint": 0, "fade": 8, "hue_shift": 0,
        "category": "社交",
    },
    "xiaohongshu": {
        "label_zh": "小红书风",
        "description": "明亮通透，偏冷白，略褪色，柔光质感，白嫩肤色",
        "brightness": 0.2, "contrast": 5, "saturation": 10, "temperature": -5,
        "sharpness": -5, "highlights": 10, "shadows": 10,
        "vignette": 0, "grain": 0, "tint": 0, "fade": 12, "hue_shift": 0,
        "category": "社交",
    },
    # ── 艺术 ──────────────────────────────────────────────
    "morandi": {
        "label_zh": "莫兰迪",
        "description": "大幅降饱和，灰调高级感，柔和静谧，褪色效果",
        "brightness": 0.0, "contrast": -5, "saturation": -50, "temperature": 0,
        "sharpness": 0, "highlights": -5, "shadows": 5,
        "vignette": 0, "grain": 0, "tint": 0, "fade": 25, "hue_shift": 0,
        "category": "艺术",
    },
}

# All parameter names and their ranges
PARAM_SPEC = {
    "brightness":   {"min": -1.0, "max": 1.0,  "step": 0.1,  "label": "亮度",   "default": 0.0},
    "contrast":     {"min": -50,  "max": 50,   "step": 5,    "label": "对比度", "default": 0},
    "saturation":   {"min": -50,  "max": 50,   "step": 5,    "label": "饱和度", "default": 0},
    "temperature":  {"min": -50,  "max": 50,   "step": 5,    "label": "色温",   "default": 0},
    "sharpness":    {"min": -50,  "max": 50,   "step": 5,    "label": "锐度",   "default": 0},
    "highlights":   {"min": -50,  "max": 50,   "step": 5,    "label": "高光",   "default": 0},
    "shadows":      {"min": -50,  "max": 50,   "step": 5,    "label": "阴影",   "default": 0},
    "vignette":     {"min": 0,    "max": 100,  "step": 5,    "label": "暗角",   "default": 0},
    "grain":        {"min": 0,    "max": 100,  "step": 5,    "label": "颗粒",   "default": 0},
    "tint":         {"min": -50,  "max": 50,   "step": 5,    "label": "色调",   "default": 0},
    "fade":         {"min": 0,    "max": 100,  "step": 5,    "label": "褪色",   "default": 0},
    "hue_shift":    {"min": -30,  "max": 30,   "step": 5,    "label": "色相偏移","default": 0},
}

# Parameter keys in application order
PARAM_KEYS = ["brightness", "contrast", "saturation", "temperature",
              "sharpness", "highlights", "shadows", "vignette",
              "grain", "tint", "fade", "hue_shift"]


class EditingService:
    def __init__(self):
        self.image_service = ImageService()
        self.analysis_service = AnalysisService()

    # ── Public API ──────────────────────────────────────────

    @classmethod
    def get_available_styles(cls) -> List[dict]:
        """Return all available style presets with metadata (for frontend)."""
        return [
            {
                "id": style_id,
                "label_zh": cfg["label_zh"],
                "description": cfg["description"],
                "category": cfg["category"],
                "params": {k: cfg.get(k, PARAM_SPEC[k]["default"]) for k in PARAM_KEYS},
            }
            for style_id, cfg in STYLE_PRESETS.items()
        ]

    @classmethod
    def get_style_params(cls, style_id: str) -> Optional[dict]:
        """Return the default params for a given style (or None if not found)."""
        cfg = STYLE_PRESETS.get(style_id)
        if not cfg:
            return None
        return {
            "id": style_id,
            "label_zh": cfg["label_zh"],
            "description": cfg["description"],
            "category": cfg["category"],
            **{k: cfg.get(k, PARAM_SPEC[k]["default"]) for k in PARAM_KEYS},
        }

    @classmethod
    def get_param_spec(cls) -> dict:
        """Return parameter metadata (ranges, labels, defaults) for frontend."""
        return PARAM_SPEC

    async def apply_edits(
        self,
        image_id: str,
        brightness: float = 0.0,
        contrast: float = 0.0,
        saturation: float = 0.0,
        temperature: float = 0.0,
        sharpness: float = 0.0,
        highlights: float = 0.0,
        shadows: float = 0.0,
        vignette: float = 0.0,
        grain: float = 0.0,
        tint: float = 0.0,
        fade: float = 0.0,
        hue_shift: float = 0.0,
        style: Optional[str] = None,
        style_overrides: Optional[dict] = None,
    ) -> Dict:
        """Apply edits to image. All params optional, defaults to 0 (no change).

        If `style` is given, preset params are loaded first,
        then `style_overrides` override specific params,
        then explicit keyword args override everything.
        """
        image_path = await self.image_service.get_image_path(image_id)
        if not image_path:
            raise ValueError("Image not found")

        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Failed to load image")

        # ── Resolve final params ────────────────────────────
        final: Dict[str, float] = {}

        # Start from style preset
        if style and style in STYLE_PRESETS:
            cfg = STYLE_PRESETS[style]
            for k in PARAM_KEYS:
                final[k] = cfg.get(k, PARAM_SPEC[k]["default"])

        # Apply style_overrides
        if style_overrides:
            for k in PARAM_KEYS:
                if k in style_overrides:
                    final[k] = float(style_overrides[k])

        # Apply explicit keyword args (clamp to spec)
        kw = locals()
        for k in PARAM_KEYS:
            if k in kw and kw[k] is not None and float(kw[k]) != 0.0:
                final[k] = float(kw[k])

        # Ensure all keys exist with defaults
        for k in PARAM_KEYS:
            if k not in final:
                final[k] = PARAM_SPEC[k]["default"]

        # Clamp all values
        for k in PARAM_KEYS:
            spec = PARAM_SPEC[k]
            final[k] = max(spec["min"], min(spec["max"], final[k]))

        # ── Apply in order ──────────────────────────────────
        edited = image.copy()

        if final["brightness"] != 0:
            edited = self._adjust_brightness(edited, final["brightness"])
        if final["contrast"] != 0:
            edited = self._adjust_contrast(edited, final["contrast"])
        if final["saturation"] != 0:
            edited = self._adjust_saturation(edited, final["saturation"])
        if final["temperature"] != 0:
            edited = self._adjust_temperature(edited, final["temperature"])
        if final["tint"] != 0:
            edited = self._adjust_tint(edited, final["tint"])
        if final["hue_shift"] != 0:
            edited = self._adjust_hue_shift(edited, final["hue_shift"])
        if final["highlights"] != 0 or final["shadows"] != 0:
            edited = self._adjust_highlights_shadows(edited, final["highlights"], final["shadows"])
        if final["sharpness"] != 0:
            edited = self._adjust_sharpness(edited, final["sharpness"])
        if final["fade"] != 0:
            edited = self._adjust_fade(edited, final["fade"])
        if final["vignette"] != 0:
            edited = self._adjust_vignette(edited, final["vignette"])
        if final["grain"] != 0:
            edited = self._adjust_grain(edited, final["grain"])

        edited_image_id = await self.image_service.save_edited_image(edited, image_id)

        return {
            "original_image_id": image_id,
            "edited_image_id": edited_image_id,
            "edits_applied": {k: final[k] for k in PARAM_KEYS},
            "preview_url": f"/api/v1/images/{edited_image_id}",
        }

    async def auto_enhance(self, image_id: str) -> Dict:
        """Auto-enhance image based on analysis with severity-graded force."""
        analysis = await self.analysis_service.analyze_image(image_id)

        enhancements = {k: 0.0 for k in PARAM_KEYS}
        for issue in analysis["issues"]:
            severity = float(issue.get("severity_score", 0.5))
            if issue["type"] == "underexposed":
                # brightness 0.3~0.6, shadows 15~35, contrast 0~15
                enhancements["brightness"] = 0.3 + severity * 0.3
                enhancements["shadows"] = 15.0 + severity * 20.0
                enhancements["contrast"] = severity * 15.0
            elif issue["type"] == "overexposed":
                # brightness -0.3~-0.6, highlights -15~-35
                enhancements["brightness"] = -(0.3 + severity * 0.3)
                enhancements["highlights"] = -(15.0 + severity * 20.0)
            elif issue["type"] == "low_contrast":
                # contrast 15~40, sharpness 10~25
                enhancements["contrast"] = 15.0 + severity * 25.0
                enhancements["sharpness"] = 10.0 + severity * 15.0
            elif issue["type"] == "undersaturated":
                # saturation 15~40
                enhancements["saturation"] = 15.0 + severity * 25.0

        return await self.apply_edits(image_id=image_id, **enhancements)

    async def compare_images(self, image_id: str) -> Dict:
        return {
            "original": f"/api/v1/images/{image_id}",
            "edited": f"/api/v1/images/{image_id}_edited",
            "differences": {"brightness_change": 0.2, "contrast_change": 15, "saturation_change": 10},
        }

    # ═══════════════════════════════════════════════════════════
    #  Low-level adjustment algorithms (12 total)
    # ═══════════════════════════════════════════════════════════

    # ── 1. Brightness ────────────────────────────────────────
    def _adjust_brightness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -1.0 to 1.0, multiplicative scaling."""
        img = image.astype(np.float32) * (1.0 + factor)
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 2. Contrast ─────────────────────────────────────────
    def _adjust_contrast(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 to 50, stretch around mean."""
        img = image.astype(np.float32)
        mean = np.mean(img)
        img = (img - mean) * (1.0 + factor / 100.0) + mean
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 3. Saturation ───────────────────────────────────────
    def _adjust_saturation(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 to 50, HSV saturation channel."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= (1.0 + factor / 100.0)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # ── 4. Temperature (Blue ↔ Amber) ───────────────────────
    def _adjust_temperature(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 (cool/blue) to +50 (warm/amber)."""
        img = image.astype(np.float32)
        if factor > 0:  # Warmer: boost red, reduce blue
            img[:, :, 2] *= (1.0 + factor / 100.0)
            img[:, :, 0] *= (1.0 - factor / 200.0)
        else:  # Cooler: boost blue, reduce red
            img[:, :, 0] *= (1.0 + abs(factor) / 100.0)
            img[:, :, 2] *= (1.0 - abs(factor) / 200.0)
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 5. Sharpness ────────────────────────────────────────
    def _adjust_sharpness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 (soften/blur) to +50 (sharpen).

        Positive: unsharp mask (Gaussian blur subtract).
        Negative: Gaussian blur of increasing kernel size.
        """
        if factor > 0:
            # Unsharp mask
            intensity = factor / 50.0  # 0..1
            sigma = 0.5 + intensity * 2.0
            blurred = cv2.GaussianBlur(image, (0, 0), sigma)
            img = cv2.addWeighted(image, 1.0 + intensity * 0.8, blurred, -intensity * 0.8, 0)
            return img
        else:
            # Soften
            intensity = abs(factor) / 50.0  # 0..1
            sigma = intensity * 3.0
            if sigma < 0.3:
                return image
            ksize = int(sigma * 4) | 1  # odd
            ksize = max(3, ksize)
            return cv2.GaussianBlur(image, (ksize, ksize), sigma)

    # ── 6. Highlights ───────────────────────────────────────
    def _adjust_highlights(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 (darken highlights) to +50 (brighten highlights).

        Uses a luminance-weighted mask: pixels above mid-gray are affected more.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # Mask: smoothstep from 0.4 to 0.7 luminance
        mask = np.clip((gray - 0.4) / 0.3, 0.0, 1.0)
        # Apply: brighten or darken proportionally to mask
        img = image.astype(np.float32)
        delta = factor / 50.0 * 0.4  # max ±40% effect on highlights
        img += img * delta * mask[:, :, np.newaxis]
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 7. Shadows ──────────────────────────────────────────
    def _adjust_shadows(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 (darken shadows) to +50 (lift shadows).

        Uses an inverted luminance mask: pixels below mid-gray are affected more.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        # Mask: smoothstep from 0.6 down to 0.3 luminance (inverted)
        mask = np.clip((0.6 - gray) / 0.3, 0.0, 1.0)
        img = image.astype(np.float32)
        delta = factor / 50.0 * 0.4
        img += img * delta * mask[:, :, np.newaxis]
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 8. Highlights + Shadows (combined, more efficient) ──
    def _adjust_highlights_shadows(self, image: np.ndarray,
                                    hl_factor: float, sh_factor: float) -> np.ndarray:
        """Combined highlights and shadows adjustment in one pass."""
        if hl_factor == 0 and sh_factor == 0:
            return image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

        # Highlights mask (bright areas)
        hl_mask = np.clip((gray - 0.4) / 0.3, 0.0, 1.0)
        # Shadows mask (dark areas)
        sh_mask = np.clip((0.6 - gray) / 0.3, 0.0, 1.0)

        img = image.astype(np.float32)
        hl_delta = hl_factor / 50.0 * 0.4
        sh_delta = sh_factor / 50.0 * 0.4

        img += img * hl_delta * hl_mask[:, :, np.newaxis]
        img += img * sh_delta * sh_mask[:, :, np.newaxis]

        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 9. Vignette ─────────────────────────────────────────
    def _adjust_vignette(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: 0 to 100, darkening of image edges/corners."""
        if factor <= 0:
            return image

        h, w = image.shape[:2]
        intensity = factor / 100.0

        # Create radial gradient
        cx, cy = w / 2.0, h / 2.0
        max_r = np.sqrt(cx ** 2 + cy ** 2)
        y, x = np.ogrid[:h, :w]
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        # Normalize: 1.0 at center, 0.0 at corners (then we invert)
        vignette = 1.0 - np.clip(r / max_r, 0.0, 1.0)
        # Shape it: power curve for more natural falloff
        vignette = vignette ** 1.5
        # Invert: 1.0 at corners (full darkening), 0.0 at center (no change)
        darken = (1.0 - vignette) * intensity * 0.7

        img = image.astype(np.float32)
        for c in range(3):
            img[:, :, c] *= (1.0 - darken)

        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 10. Film Grain ──────────────────────────────────────
    def _adjust_grain(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: 0 to 100, add monochrome film grain noise."""
        if factor <= 0:
            return image

        h, w = image.shape[:2]
        intensity = factor / 100.0 * 30.0  # max ±30 pixel variation

        # Generate Gaussian noise
        noise = np.random.randn(h, w).astype(np.float32) * intensity
        # Slight blur on noise for more natural grain look
        noise = cv2.GaussianBlur(noise, (3, 3), 0.8)

        img = image.astype(np.float32)
        for c in range(3):
            img[:, :, c] += noise

        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 11. Tint (Green ↔ Magenta) ──────────────────────────
    def _adjust_tint(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -50 (green) to +50 (magenta).

        Magenta = red + blue, so boost R+B and reduce G.
        Green = boost G and reduce R+B.
        """
        img = image.astype(np.float32)
        if factor > 0:  # Magenta
            scale = factor / 100.0
            img[:, :, 2] *= (1.0 + scale)      # Red+
            img[:, :, 0] *= (1.0 + scale * 0.5) # Blue+
            img[:, :, 1] *= (1.0 - scale)       # Green-
        else:  # Green
            scale = abs(factor) / 100.0
            img[:, :, 1] *= (1.0 + scale)       # Green+
            img[:, :, 2] *= (1.0 - scale * 0.5) # Red-
            img[:, :, 0] *= (1.0 - scale * 0.5) # Blue-
        return np.clip(img, 0, 255).astype(np.uint8)

    # ── 12. Fade (Lift Blacks) ─────────────────────────────
    def _adjust_fade(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: 0 to 100. Lifts the black point for a faded/matte look.

        Maps [0, 255] → [lift, 255] where lift = factor * 2.55.
        Then applies an S-curve to keep highlights natural.
        """
        if factor <= 0:
            return image

        lift = factor / 100.0 * 0.35  # max 35% black lift

        img = image.astype(np.float32) / 255.0

        # Apply lift: remap [0,1] → [lift, 1]
        img = img * (1.0 - lift) + lift

        # Soft S-curve to prevent highlights from clipping
        # Keep mids natural, slightly compress highlights
        img = np.power(img, 0.95)

        return np.clip(img * 255.0, 0, 255).astype(np.uint8)

    # ── 13. Hue Shift ───────────────────────────────────────
    def _adjust_hue_shift(self, image: np.ndarray, factor: float) -> np.ndarray:
        """factor: -30 to +30 degrees. Global hue rotation in HSV space."""
        if factor == 0:
            return image

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        # H is 0-180 in OpenCV (half of 360)
        shift = factor / 2.0  # convert degrees to OpenCV H units
        hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180.0
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
