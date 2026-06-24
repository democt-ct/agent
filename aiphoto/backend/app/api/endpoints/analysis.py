from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.analysis_service import AnalysisService

router = APIRouter()

class AnalysisRequest(BaseModel):
    image_id: str

class Issue(BaseModel):
    type: str
    severity: str
    description: str

class AnalysisResponse(BaseModel):
    image_id: str
    scene: str
    objects: List[str]
    lighting: str
    quality: str
    issues: List[Issue]
    suggestions: List[str]

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(request: AnalysisRequest):
    """Analyze an image for issues and suggestions"""
    analysis_service = AnalysisService()
    
    try:
        result = await analysis_service.analyze_image(request.image_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/{image_id}/report")
async def get_analysis_report(image_id: str):
    """Get analysis report for an image"""
    analysis_service = AnalysisService()
    
    try:
        report = await analysis_service.get_report(image_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")