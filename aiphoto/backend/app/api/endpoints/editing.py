from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.editing_service import EditingService

router = APIRouter()

class EditRequest(BaseModel):
    image_id: str
    brightness: Optional[float] = 0.0
    contrast: Optional[float] = 0.0
    saturation: Optional[float] = 0.0
    temperature: Optional[float] = 0.0
    sharpness: Optional[float] = 0.0
    highlights: Optional[float] = 0.0
    shadows: Optional[float] = 0.0
    vignette: Optional[float] = 0.0
    grain: Optional[float] = 0.0
    tint: Optional[float] = 0.0
    fade: Optional[float] = 0.0
    hue_shift: Optional[float] = 0.0
    style: Optional[str] = None
    style_overrides: Optional[dict] = None

class EditResponse(BaseModel):
    original_image_id: str
    edited_image_id: str
    edits_applied: Dict
    preview_url: str

@router.post("/apply", response_model=EditResponse)
async def apply_edits(request: EditRequest):
    """Apply edits to an image"""
    editing_service = EditingService()

    try:
        result = await editing_service.apply_edits(
            image_id=request.image_id,
            brightness=request.brightness,
            contrast=request.contrast,
            saturation=request.saturation,
            temperature=request.temperature,
            sharpness=request.sharpness,
            highlights=request.highlights,
            shadows=request.shadows,
            vignette=request.vignette,
            grain=request.grain,
            tint=request.tint,
            fade=request.fade,
            hue_shift=request.hue_shift,
            style=request.style,
            style_overrides=request.style_overrides,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Editing failed: {str(e)}")

@router.post("/auto-enhance")
async def auto_enhance(image_id: str):
    """Auto-enhance an image"""
    editing_service = EditingService()

    try:
        result = await editing_service.auto_enhance(image_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-enhance failed: {str(e)}")

@router.get("/{image_id}/compare")
async def compare_images(image_id: str):
    """Compare original and edited images"""
    editing_service = EditingService()

    try:
        comparison = await editing_service.compare_images(image_id)
        return comparison
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

# ── Parameter spec endpoint ────────────────────────────────

@router.get("/param-spec")
async def get_param_spec():
    """Return parameter metadata (ranges, labels) for frontend sliders."""
    return EditingService.get_param_spec()
