from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.preset_service import PresetService
from app.services.editing_service import EditingService, PARAM_KEYS

router = APIRouter()

preset_svc = PresetService()


# ── Pydantic models ────────────────────────────────────────

class PresetCreate(BaseModel):
    name: str
    brightness: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    temperature: float = 0.0
    sharpness: float = 0.0
    highlights: float = 0.0
    shadows: float = 0.0
    vignette: float = 0.0
    grain: float = 0.0
    tint: float = 0.0
    fade: float = 0.0
    hue_shift: float = 0.0


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    brightness: Optional[float] = None
    contrast: Optional[float] = None
    saturation: Optional[float] = None
    temperature: Optional[float] = None
    sharpness: Optional[float] = None
    highlights: Optional[float] = None
    shadows: Optional[float] = None
    vignette: Optional[float] = None
    grain: Optional[float] = None
    tint: Optional[float] = None
    fade: Optional[float] = None
    hue_shift: Optional[float] = None


class PresetOut(BaseModel):
    id: str
    name: str
    brightness: float
    contrast: float
    saturation: float
    temperature: float
    sharpness: float
    highlights: float
    shadows: float
    vignette: float
    grain: float
    tint: float
    fade: float
    hue_shift: float
    created_at: str


def _preset_to_style(p: dict) -> dict:
    """Convert a stored preset dict to the style-info shape for frontend."""
    return {
        "id": p["id"],
        "label_zh": p["name"],
        "description": "自定义预设",
        "category": "自定义",
        "params": {k: p.get(k, 0) for k in PARAM_KEYS},
    }


# ── Style info (built-in + custom) ─────────────────────────

@router.get("/styles")
async def list_styles():
    """Return all built-in styles + custom presets."""
    builtin = EditingService.get_available_styles()
    custom = preset_svc.list()
    return {
        "builtin": builtin,
        "custom": [_preset_to_style(p) for p in custom],
    }


@router.get("/styles/{style_id}")
async def get_style(style_id: str):
    """Get a single style's params (built-in or custom)."""
    params = EditingService.get_style_params(style_id)
    if params:
        return params
    preset = preset_svc.get(style_id)
    if preset:
        return {
            "id": preset["id"],
            "label_zh": preset["name"],
            "description": "自定义预设",
            "category": "自定义",
            **{k: preset.get(k, 0) for k in PARAM_KEYS},
        }
    raise HTTPException(status_code=404, detail="Style not found")


# ── Custom preset CRUD ─────────────────────────────────────

@router.get("/presets", response_model=List[PresetOut])
async def list_presets():
    return preset_svc.list()


@router.post("/presets", response_model=PresetOut)
async def create_preset(body: PresetCreate):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    kwargs = {k: getattr(body, k) for k in PARAM_KEYS}
    preset = preset_svc.create(name=body.name.strip(), **kwargs)
    return preset


@router.put("/presets/{preset_id}", response_model=PresetOut)
async def update_preset(preset_id: str, body: PresetUpdate):
    kwargs = {k: getattr(body, k) for k in PARAM_KEYS}
    if body.name is not None:
        kwargs["name"] = body.name
    preset = preset_svc.update(preset_id, **kwargs)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    ok = preset_svc.delete(preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"status": "deleted"}
