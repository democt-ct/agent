import re, json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.vision_service import VisionService
from app.services.image_service import ImageService
from app.services.editing_service import EditingService, STYLE_PRESETS, PARAM_KEYS
from app.services.analysis_service import AnalysisService
from app.services.history_service import HistoryService

router = APIRouter()
history_svc = HistoryService()


def _preference_hint() -> str:
    """读取用户长期偏好，生成注入 prompt 的提示文本。"""
    prefs = history_svc.get_preferences()
    favs = prefs.get("favorite_styles", {})
    if favs:
        top = sorted(favs.items(), key=lambda x: -x[1])[:3]
        top_labels = [STYLE_PRESETS.get(s[0], {}).get("label_zh", s[0]) for s in top if s[0] in STYLE_PRESETS]
        if top_labels:
            return f"\n【用户偏好提示】该用户最常使用的风格：{'、'.join(top_labels)}，可优先考虑但不必强制。\n"
    return ""

_STYLE_LIST = "、".join([f"{sid}({cfg['label_zh']})" for sid, cfg in STYLE_PRESETS.items()])


class ChatRequest(BaseModel):
    message: str
    image_id: Optional[str] = None
    # 链式编辑：上一次编辑结果作为本次起点（支持「再亮一点」累加调整）
    current_image_id: Optional[str] = None
    # 会话 ID（可选，传入则自动记录消息历史）
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    image_id: Optional[str] = None
    # 结构化数据（供前端可视化，不再依赖正则解析文本）
    params: Optional[dict] = None
    diagnosis: Optional[dict] = None
    applied_params: Optional[dict] = None
    source_image_id: Optional[str] = None  # 本次编辑的起点（链式追踪）


PROMPT_EDIT = (
    "你是一个专业的大胆的智能修图助手。用户发来一张图片和修图需求。\n"
    "\n"
    "第一步：仔细观察这张图片的特征：\n"
    "  - 当前曝光状况（过曝/欠曝/正常）\n"
    "  - 色调偏向（偏暖/偏冷/中性）\n"
    "  - 拍摄场景（人像/风景/美食/街拍/室内/夜景等）\n"
    "  - 现有问题（色偏、噪点、对比度不足等）\n"
    "\n"
    "第二步：结合用户需求和图片特征，输出有视觉冲击力的修图参数。\n"
    "参数字段：\n"
    "  brightness(-1~1)、contrast(-50~50)、saturation(-50~50)、temperature(-50~50暖)\n"
    "  sharpness(-50柔~50锐)、highlights(-50~50)、shadows(-50~50)、vignette(0~100)\n"
    "  grain(0~100)、tint(-50绿~50洋红)、fade(0~100)、hue_shift(-30~30)\n"
    "  style: 可选风格基底，或 null：\n"
    f"    {_STYLE_LIST}\n"
    "\n"
    "⚠️⚠️⚠️ 核心要求 — 调色要有明确视觉冲击力，不能让人感觉「几乎没变化」：\n"
    "  1. 参数振幅下限：brightness 若需调整应在 ±0.2 以上才有感觉；contrast 在 ±20 以上才明显\n"
    "  2. 不要所有参数都用小数值！宁可 3~5 个参数用大值，也不要 12 个参数全是 ±3 以内\n"
    "  3. 组合使用参数制造「质感」：\n"
    "     通透感 = highlights-15 + shadows+20 + contrast+15 + sharpness+10（同时用）\n"
    "     电影感 = brightness-0.2 + contrast+30 + temperature-20 + vignette+35（同时用）\n"
    "     小清新 = brightness+0.3 + contrast-10 + saturation-5 + shadows+15 + fade+15\n"
    "     深沉感 = brightness-0.3 + contrast+35 + highlights-20 + vignette+40\n"
    "  4. 要让人一眼看出这张图被「AI调过了」— 有想法、有方向、有力度\n"
    "  5. 如果图片本身已经偏暖，电影感风格就不要再加那么多冷色；过曝则减少brightness\n"
    "\n"
    "📊 场景-力度参考表（基于图片实际特征选择合适的力度）：\n"
    "  欠曝人像   → brightness+0.3~0.5, shadows+20~30, highlights-10, contrast+10\n"
    "  过曝户外   → brightness-0.2~0.4, highlights-20~30, contrast+15, saturation+5\n"
    "  灰暗风景   → contrast+25~40, saturation+15~25, sharpness+15~20, shadows+10\n"
    "  室内暖光   → temperature-15~25(拉回色温平衡), contrast+10, highlights-10\n"
    "  夜景城市   → contrast+30~45, brightness-0.1~0.2, vignette+25~40, sharpness+15~25\n"
    "  食物静物   → temperature+10~20(暖色增食欲), saturation+10~20, sharpness+10, highlights-5\n"
    "  人像特写   → brightness+0.1~0.2, shadows+10~20, sharpness-5~10(柔肤), contrast-5~5\n"
    "\n"
    "回复格式（===JSON===分隔，JSON在最后单独一行）：\n"
    "修图分析和说明（2-3句中文，解释为什么这样调）...\n"
    "===JSON===\n"
    '{"brightness":<-1到1>,"contrast":<-50到50>,"saturation":<-50到50>,"temperature":<-50到50>,"sharpness":<-50到50>,"highlights":<-50到50>,"shadows":<-50到50>,"vignette":<0到100>,"grain":<0到100>,"tint":<-50到50>,"fade":<0到100>,"hue_shift":<-30到30>,"style":"<风格id或null>"}\n'
)

PROMPT_ANALYZE = (
    "请详细描述这张图片，包括内容、光线、构图、色彩，并指出可以改进的地方。用中文回复，保持友好专业，约3-5句话。"
)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    vision = VisionService()
    image_svc = ImageService()
    editing = EditingService()
    analysis_svc = AnalysisService()

    # 链式编辑：优先用 current_image_id（上次结果），否则用 image_id（原始上传）
    # 这样新上传的图会重置链；之后的「再亮一点」基于上次结果累加
    source_image_id = request.current_image_id or request.image_id
    image_path = None
    if source_image_id:
        image_path = await image_svc.get_image_path(source_image_id)
        if not image_path and request.image_id:
            # current_image_id 失效时回退到原始图
            source_image_id = request.image_id
            image_path = await image_svc.get_image_path(source_image_id)
        if not image_path:
            raise HTTPException(status_code=404, detail="Image not found")

    msg = request.message.strip()
    new_image_id: Optional[str] = None
    reply: str

    if not image_path:
        reply = await vision.chat(
            "用户说：" + msg + "\n你是修图助手，请友好回复。如果有任何不清楚的，可以询问用户。",
            None,
        )
        return ChatResponse(reply=reply, image_id=None)

    # Detect "just analyze" intent
    analyze_keywords = ["分析", "看看", "describe", "analyze", "描述", "怎么样", "评估"]
    if any(kw in msg.lower() for kw in analyze_keywords):
        ai_reply = await vision.chat(PROMPT_ANALYZE, image_path)
        return ChatResponse(reply=ai_reply, image_id=None, source_image_id=source_image_id)

    # AI-driven editing — inject image diagnosis data
    diagnosis: dict = {}
    diagnosis_text = ""
    if image_path:
        try:
            diagnosis = analysis_svc.quick_diagnose(image_path)
            diagnosis_text = (
                f"【图像诊断数据 — 请根据这些真实像素统计制定调色方案】\n"
                f"- 平均亮度：{diagnosis['brightness_mean']}/255"
                f"（{'偏暗，需要提亮' if diagnosis['brightness_mean'] < 100 else '偏亮，需要压暗' if diagnosis['brightness_mean'] > 155 else '正常'}）\n"
                f"- 对比度标准差：{diagnosis['contrast_std']}"
                f"（{'偏低，需增强' if diagnosis['contrast_std'] < 40 else '正常'}）\n"
                f"- 平均饱和度：{diagnosis['saturation_mean']}"
                f"（{'偏灰，需增强' if diagnosis['saturation_mean'] < 60 else '正常'}）\n"
                f"- 检测到的问题：{diagnosis['issues_text']}\n"
                f"- 场景推测：{diagnosis['scene_hint']}\n"
            )
        except Exception:
            pass  # Silent fallback — AI works without diagnosis

    ai_response = await vision.chat(diagnosis_text + _preference_hint() + msg + "\n\n" + PROMPT_EDIT, image_path)

    # Handle fallback markers (API unavailable)
    if ai_response.startswith("[STYLE:") or ai_response == "[AUTO_ENHANCE]":
        try:
            if ai_response.startswith("[STYLE:"):
                style_name = ai_response.replace("[STYLE:", "").replace("]", "").strip()
                result = await editing.apply_edits(image_id=source_image_id, style=style_name)
                new_image_id = result["edited_image_id"]
                style_label = STYLE_PRESETS.get(style_name, {}).get("label_zh", style_name)
                reply = f"已应用{style_label}风格 ✨"
            else:
                result = await editing.auto_enhance(source_image_id)
                new_image_id = result["edited_image_id"]
                reply = "已自动优化图片 ⚡"
            return ChatResponse(
                reply=reply, image_id=new_image_id,
                applied_params=result["edits_applied"],
                diagnosis=diagnosis or None,
                source_image_id=source_image_id,
            )
        except Exception as edit_err:
            return ChatResponse(reply=f"编辑失败: {str(edit_err)[:100]}", image_id=None)

    # Split explanation from JSON
    explanation: str
    params: dict

    if "===JSON===" in ai_response:
        parts = ai_response.split("===JSON===", 1)
        explanation = parts[0].strip()
        json_str = parts[1].strip()
    else:
        explanation = ""
        json_str = ai_response

    # Extract JSON
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", json_str)
        cleaned = re.sub(r"```\s*$", "", cleaned)
        json_match = re.search(r"\{[^{}]*\}", cleaned)
        if json_match:
            params = json.loads(json_match.group())
        else:
            params = json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        fallback = await vision.chat(PROMPT_ANALYZE, image_path)
        return ChatResponse(reply=fallback, image_id=None, source_image_id=source_image_id)

    # Extract all parameters from AI response
    style = params.get("style") or None
    if style and style not in STYLE_PRESETS:
        style = None

    # Build kwargs from params dict
    kwargs: dict = {}
    for k in PARAM_KEYS:
        if k in params:
            kwargs[k] = float(params[k])

    kwargs["style"] = style

    # Build reply text
    if not explanation:
        style_label = STYLE_PRESETS.get(style, {}).get("label_zh", "") if style else ""
        explanation = "根据你的要求，已调整图片。"
        if style_label:
            explanation += f" 应用风格：{style_label}。"

    # Apply edits — 以 source_image_id 为起点（链式累加）
    try:
        result = await editing.apply_edits(image_id=source_image_id, **kwargs)
        new_image_id = result["edited_image_id"]
        # Append param summary
        edits = result["edits_applied"]
        applied = []
        for k in PARAM_KEYS:
            v = edits.get(k, 0)
            if v != 0:
                label = {
                    "brightness": "亮度", "contrast": "对比度", "saturation": "饱和度",
                    "temperature": "色温", "sharpness": "锐度", "highlights": "高光",
                    "shadows": "阴影", "vignette": "暗角", "grain": "颗粒",
                    "tint": "色调", "fade": "褪色", "hue_shift": "色相偏移",
                }.get(k, k)
                applied.append(f"{label}{v:+.0f}" if isinstance(v, float) and v == int(v) else f"{label}{v:+.1f}")
        if applied:
            explanation += "\n" + " ".join(applied)
    except Exception as edit_err:
        explanation += f"\n（编辑失败：{str(edit_err)[:100]}）"
        return ChatResponse(
            reply=explanation, image_id=None, params=params,
            diagnosis=diagnosis or None, source_image_id=source_image_id,
        )

    # ── 记录历史（静默失败，不影响主流程）──
    if request.session_id:
        try:
            history_svc.append_message(
                request.session_id, "user", msg,
                image_id=request.image_id,
            )
            history_svc.append_message(
                request.session_id, "assistant", explanation,
                image_id=new_image_id, params=result["edits_applied"],
                diagnosis=diagnosis or None,
            )
            history_svc.record_edit(
                style=style, params=result["edits_applied"],
            )
        except Exception:
            pass  # History failure must not break chat

    return ChatResponse(
        reply=explanation, image_id=new_image_id,
        params=params, applied_params=result["edits_applied"],
        diagnosis=diagnosis or None, source_image_id=source_image_id,
    )
