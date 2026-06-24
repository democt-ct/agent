import cv2
import numpy as np
from typing import Dict, List
from app.services.image_service import ImageService
from app.services.vision_service import VisionService


class AnalysisService:
    def __init__(self):
        self.image_service = ImageService()
        self.vision_service = VisionService()
    
    async def analyze_image(self, image_id: str) -> Dict:
        """Analyze image for quality issues"""
        image_path = await self.image_service.get_image_path(image_id)
        if not image_path:
            raise ValueError("Image not found")
        
        # Use ModelScope vision model for analysis
        try:
            vision_result = await self.vision_service.analyze_image(image_path)
            
            # Load image for additional analysis
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Failed to load image")
            
            # Convert to RGB for analysis
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Combine vision model results with OpenCV analysis
            analysis = {
                "image_id": image_id,
                "scene": vision_result.get("scene", self._detect_scene(rgb_image)),
                "objects": vision_result.get("objects", self._detect_objects(rgb_image)),
                "lighting": self._analyze_lighting(rgb_image),
                "quality": vision_result.get("quality", self._analyze_quality(rgb_image)),
                "issues": self._find_issues(rgb_image),
                "suggestions": vision_result.get("suggestions", self._generate_suggestions(rgb_image)),
                "caption": vision_result.get("caption", "")
            }
            
            return analysis
            
        except Exception as e:
            # Fallback to OpenCV-only analysis if vision model fails
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Failed to load image")
            
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            analysis = {
                "image_id": image_id,
                "scene": self._detect_scene(rgb_image),
                "objects": self._detect_objects(rgb_image),
                "lighting": self._analyze_lighting(rgb_image),
                "quality": self._analyze_quality(rgb_image),
                "issues": self._find_issues(rgb_image),
                "suggestions": self._generate_suggestions(rgb_image),
                "caption": "Analysis performed using OpenCV only"
            }
            
            return analysis
    
    def _detect_scene(self, image: np.ndarray) -> str:
        """Detect scene type (simplified)"""
        # This is a placeholder - in real implementation, use a trained model
        return "landscape"
    
    def _detect_objects(self, image: np.ndarray) -> List[str]:
        """Detect objects in image (simplified)"""
        # This is a placeholder - in real implementation, use object detection
        return ["sky", "grass", "mountain"]
    
    def _analyze_lighting(self, image: np.ndarray) -> str:
        """Analyze lighting conditions"""
        # Calculate brightness
        brightness = np.mean(image)
        
        if brightness < 85:
            return "dark"
        elif brightness > 170:
            return "bright"
        else:
            return "normal"
    
    def _analyze_quality(self, image: np.ndarray) -> str:
        """Analyze image quality"""
        # Calculate Laplacian variance (blur detection)
        laplacian_var = cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
        
        if laplacian_var < 100:
            return "blurry"
        elif laplacian_var > 1000:
            return "sharp"
        else:
            return "medium"
    
    def _find_issues(self, image: np.ndarray) -> List[Dict]:
        """Find image issues with severity_score (0~1 float for force grading)."""
        issues = []
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        # Check brightness with severity_score
        brightness = np.mean(gray)
        if brightness < 85:
            severity = min(1.0, (85 - brightness) / 55.0)  # 85→0.0, 30→1.0
            issues.append({
                "type": "underexposed",
                "severity": "high" if severity > 0.6 else ("medium" if severity > 0.3 else "low"),
                "severity_score": round(severity, 2),
                "description": "Image is too dark"
            })
        elif brightness > 170:
            severity = min(1.0, (brightness - 170) / 55.0)  # 170→0.0, 225→1.0
            issues.append({
                "type": "overexposed",
                "severity": "high" if severity > 0.6 else ("medium" if severity > 0.3 else "low"),
                "severity_score": round(severity, 2),
                "description": "Image is too bright"
            })

        # Check contrast with severity_score
        contrast = np.std(gray)
        if contrast < 30:
            severity = min(1.0, (30 - contrast) / 25.0)  # 30→0.0, 5→1.0
            issues.append({
                "type": "low_contrast",
                "severity": "high" if severity > 0.6 else ("medium" if severity > 0.3 else "low"),
                "severity_score": round(severity, 2),
                "description": "Image has low contrast"
            })

        # Check saturation with severity_score
        saturation = np.mean(hsv[:, :, 1])
        if saturation < 50:
            severity = min(1.0, (50 - saturation) / 45.0)  # 50→0.0, 5→1.0
            issues.append({
                "type": "undersaturated",
                "severity": "high" if severity > 0.6 else ("medium" if severity > 0.3 else "low"),
                "severity_score": round(severity, 2),
                "description": "Colors appear dull"
            })

        return issues
    
    def _generate_suggestions(self, image: np.ndarray) -> List[str]:
        """Generate improvement suggestions"""
        suggestions = []
        
        # Analyze and suggest improvements
        brightness = np.mean(image)
        if brightness < 85:
            suggestions.append("Increase exposure to brighten the image")
        
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        contrast = np.std(gray)
        if contrast < 30:
            suggestions.append("Enhance contrast for better visual impact")
        
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        saturation = np.mean(hsv[:, :, 1])
        if saturation < 50:
            suggestions.append("Boost saturation to make colors more vibrant")
        
        return suggestions
    
    def quick_diagnose(self, image_path: str) -> Dict:
        """Fast OpenCV-only diagnosis for AI prompt injection.
        
        Returns pixel statistics without calling VisionService API.
        """
        image = cv2.imread(image_path)
        if image is None:
            return {
                "brightness_mean": 128, "contrast_std": 30, "saturation_mean": 50,
                "issues": [], "issues_text": "无法读取图片",
                "scene_hint": "unknown",
            }

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        brightness_val = float(np.mean(gray))
        contrast_val = float(np.std(gray))
        saturation_val = float(np.mean(hsv[:, :, 1]))

        # Scene hint based on brightness + contrast + saturation patterns
        if brightness_val < 80 and contrast_val > 40:
            scene_hint = "夜景或暗光环境"
        elif brightness_val < 100:
            scene_hint = "室内或阴天场景"
        elif brightness_val > 180 and saturation_val < 50:
            scene_hint = "过曝户外/雪景/沙滩"
        elif brightness_val > 160:
            scene_hint = "明亮户外"
        elif contrast_val < 25:
            scene_hint = "雾天/逆光/低对比场景"
        elif saturation_val > 100:
            scene_hint = "高饱和场景（可能风景/花卉）"
        elif saturation_val < 40:
            scene_hint = "低饱和/灰调场景"
        else:
            scene_hint = "日常光线场景"

        # Detect issues using same logic as _find_issues
        issues_list = self._find_issues(rgb)
        issues_desc = []
        for iss in issues_list:
            t = iss["type"]
            s = iss.get("severity_score", 0.5)
            label = {
                "underexposed": f"欠曝(严重度{s:.0%})",
                "overexposed": f"过曝(严重度{s:.0%})",
                "low_contrast": f"对比度低(严重度{s:.0%})",
                "undersaturated": f"饱和度低(严重度{s:.0%})",
            }.get(t, t)
            issues_desc.append(label)

        return {
            "brightness_mean": round(brightness_val, 1),
            "contrast_std": round(contrast_val, 1),
            "saturation_mean": round(saturation_val, 1),
            "issues": issues_list,
            "issues_text": "、".join(issues_desc) if issues_desc else "无明显问题",
            "scene_hint": scene_hint,
        }

    async def get_report(self, image_id: str) -> Dict:
        """Get detailed analysis report"""
        analysis = await self.analyze_image(image_id)
        
        report = {
            "image_id": image_id,
            "summary": {
                "overall_quality": analysis["quality"],
                "issues_count": len(analysis["issues"]),
                "suggestions_count": len(analysis["suggestions"])
            },
            "details": analysis
        }
        
        return report