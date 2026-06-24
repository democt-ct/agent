from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from app.services.image_service import ImageService
from app.core.config import settings
import os

router = APIRouter()

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image for processing"""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, WebP")
    
    # Validate file size
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size: 10MB")
    
    # Save file
    image_service = ImageService()
    image_id = await image_service.save_upload(file)
    
    return {"image_id": image_id, "filename": file.filename}

@router.get("/{image_id}")
async def get_image(image_id: str):
    """Get image by ID"""
    image_service = ImageService()
    image_path = await image_service.get_image_path(image_id)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)

@router.delete("/{image_id}")
async def delete_image(image_id: str):
    """Delete image by ID"""
    image_service = ImageService()
    success = await image_service.delete_image(image_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return {"message": "Image deleted successfully"}