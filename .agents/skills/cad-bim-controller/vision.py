"""
Advanced Computer Vision for CAD/BIM Screens
===========================================
- Template matching
- OCR (Text detection)
- Icon detection
- Error detection
"""

import cv2
import numpy as np
from PIL import Image
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("CAD-BIM-Vision")


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[int, int]


class ScreenAnalyzer:
    """Screen analyzer for CAD/BIM"""
    
    def __init__(self):
        self.ocr_reader = None
        self._init_ocr()
    
    def _init_ocr(self):
        """Load OCR engine"""
        try:
            import easyocr
            self.ocr_reader = easyocr.Reader(['en', 'ar'], gpu=False)
            logger.info("OCR loaded successfully")
        except ImportError:
            logger.warning("easyocr not installed. Text detection disabled.")
    
    # ═══════════════════════════════════════════════════════
    # Template Matching
    # ═══════════════════════════════════════════════════════
    
    def find_template(self, screen: np.ndarray, template: np.ndarray, 
                      threshold: float = 0.8) -> List[DetectedObject]:
        """
        Find template on screen
        Returns all results above threshold
        """
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        objects = []
        h, w = template.shape[:2]
        
        for pt in zip(*locations[::-1]):
            conf = result[pt[1], pt[0]]
            objects.append(DetectedObject(
                label="template",
                confidence=float(conf),
                bbox=(pt[0], pt[1], w, h),
                center=(pt[0] + w//2, pt[1] + h//2)
            ))
        
        # Non-maximum suppression (NMS)
        objects = self._nms(objects, threshold=0.3)
        return objects
    
    def _nms(self, objects: List[DetectedObject], threshold: float = 0.3) -> List[DetectedObject]:
        """Prevent duplication in results"""
        if not objects:
            return []
            
        sorted_objs = sorted(objects, key=lambda x: x.confidence, reverse=True)
        kept = [sorted_objs[0]]
        
        for obj in sorted_objs[1:]:
            overlap = False
            for k in kept:
                iou = self._iou(obj.bbox, k.bbox)
                if iou > threshold:
                    overlap = True
                    break
            if not overlap:
                kept.append(obj)
        
        return kept
    
    def _iou(self, box1: Tuple, box2: Tuple) -> float:
        """Intersection over Union"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[0]+box1[2], box2[0]+box2[2])
        y2 = min(box1[1]+box1[3], box2[1]+box2[3])
        
        inter = max(0, x2-x1) * max(0, y2-y1)
        area1 = box1[2] * box1[3]
        area2 = box2[2] * box2[3]
        
        return inter / (area1 + area2 - inter + 1e-6)
    
    # ═══════════════════════════════════════════════════════
    # OCR
    # ═══════════════════════════════════════════════════════
    
    def read_all_text(self, screen: np.ndarray) -> List[dict]:
        """Read all text on screen"""
        if self.ocr_reader is None:
            return []
            
        results = self.ocr_reader.readtext(screen)
        texts = []
        for (bbox, text, conf) in results:
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            texts.append({
                "text": text,
                "confidence": conf,
                "bbox": {
                    "x": int(min(x_coords)),
                    "y": int(min(y_coords)),
                    "w": int(max(x_coords) - min(x_coords)),
                    "h": int(max(y_coords) - min(y_coords))
                }
            })
        return texts
    
    def find_text(self, screen: np.ndarray, search_text: str) -> List[dict]:
        """Find specific text"""
        all_text = self.read_all_text(screen)
        return [t for t in all_text if search_text.lower() in t["text"].lower()]
    
    # ═══════════════════════════════════════════════════════
    # Error Detection
    # ═══════════════════════════════════════════════════════
    
    def detect_error_dialog(self, screen: np.ndarray) -> Optional[dict]:
        """
        Detect if there's an error dialog on screen
        Looks for: red X icons, "Error" text, "Warning", "Failed"
        """
        # Check for common error indicators
        error_keywords = ["error", "warning", "failed", "exception", "crash", 
                         "invalid", "cannot", "unable", "خطأ", "فشل"]
        
        texts = self.read_all_text(screen)
        for t in texts:
            if any(kw in t["text"].lower() for kw in error_keywords):
                return {
                    "type": "error_dialog",
                    "message": t["text"],
                    "location": t["bbox"],
                    "confidence": t["confidence"]
                }
        
        # Check for red X icon (error indicator)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        # Red color range in HSV
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 | mask2
        
        red_pixels = cv2.countNonZero(red_mask)
        if red_pixels > 100:  # If there's a lot of red
            return {
                "type": "red_indicator",
                "message": "Red warning indicator detected",
                "red_pixels": red_pixels
            }
        
        return None
    
    # ═══════════════════════════════════════════════════════
    # UI Element Detection
    # ═══════════════════════════════════════════════════════
    
    def detect_buttons(self, screen: np.ndarray) -> List[DetectedObject]:
        """
        Detect buttons on screen using:
        - Contour detection
        - Rectangle detection
        """
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        buttons = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w)/h
            
            # Button characteristics
            if 20 < w < 400 and 10 < h < 100 and 1.5 < aspect_ratio < 8:
                buttons.append(DetectedObject(
                    label="button",
                    confidence=0.7,
                    bbox=(x, y, w, h),
                    center=(x+w//2, y+h//2)
                ))
        
        return self._nms(buttons, threshold=0.5)
    
    def detect_input_fields(self, screen: np.ndarray) -> List[DetectedObject]:
        """Detect input fields (text boxes)"""
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        
        # Look for white/light rectangles with borders
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fields = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 50 < w < 500 and 15 < h < 50:
                fields.append(DetectedObject(
                    label="input_field",
                    confidence=0.6,
                    bbox=(x, y, w, h),
                    center=(x+w//2, y+h//2)
                ))
        
        return fields