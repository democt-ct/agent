import os
import uuid
from fastapi import UploadFile
from app.core.config import settings


class ImageService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def save_upload(self, file: UploadFile) -> str:
        """Save uploaded file and return image ID"""
        image_id = str(uuid.uuid4())
        file_extension = file.filename.split(".")[-1]
        filename = f"{image_id}.{file_extension}"
        file_path = os.path.join(self.upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        return image_id
    
    async def get_image_path(self, image_id: str) -> str:
        """Get image file path by ID"""
        # Look for file with any extension
        for ext in ["jpg", "jpeg", "png", "webp"]:
            path = os.path.join(self.upload_dir, f"{image_id}.{ext}")
            if os.path.exists(path):
                return path
        return None
    
    async def delete_image(self, image_id: str) -> bool:
        """Delete image by ID"""
        path = await self.get_image_path(image_id)
        if path and os.path.exists(path):
            os.remove(path)
            return True
        return False
    
    async def save_edited_image(self, image, original_image_id: str) -> str:
        """Save edited image"""
        import cv2
        import uuid
        
        edited_id = f"{original_image_id}_edited_{str(uuid.uuid4())[:8]}"
        filename = f"{edited_id}.jpg"
        file_path = os.path.join(self.upload_dir, filename)
        
        # Save image
        cv2.imwrite(file_path, image)
        
        return edited_id