from fastapi import APIRouter
from app.api.endpoints import images, analysis, editing, chat, presets, history

api_router = APIRouter()

api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(editing.router, prefix="/editing", tags=["editing"])
api_router.include_router(presets.router, prefix="/presets", tags=["presets"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(history.router, prefix="/history", tags=["history"])