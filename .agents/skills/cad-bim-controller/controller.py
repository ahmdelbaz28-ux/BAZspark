"""
CAD/BIM AI Controller Skill
============================
ي-controls AutoCAD, Revit, ETABS via:
1. GUI Automation (pyautogui / pywinauto)
2. Computer Vision (OpenCV)
3. Native APIs (COM, .NET)
"""

import json
import time
import base64
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import logging

# Vision & GUI
import pyautogui
import cv2
import numpy as np
from PIL import Image
import mss

# Windows automation
try:
    import pywinauto
    from pywinauto import Desktop, Application
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

# CAD APIs
try:
    import win32com.client
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import clr
    DOTNET_AVAILABLE = True
except ImportError:
    DOTNET_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CAD-BIM-Controller")


class AppType(Enum):
    AUTOCAD = "autocad"
    REVIT = "revit"
    ETABS = "etabs"
    GENERIC = "generic"


@dataclass
class ScreenRegion:
    """Region on screen"""
    x: int
    y: int
    width: int
    height: int
    
    def center(self) -> tuple:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class UIElement:
    """Detected UI element"""
    text: str
    region: ScreenRegion
    confidence: float
    element_type: str  # "button", "input", "menu", "tab", etc.


class CADBIMController:
    """
    Main controller - capable of:
    - Opening any CAD/BIM program
    - Taking screenshots and analyzing them
    - Clicking buttons and typing
    - Connecting to internal APIs
    """
    
    def __init__(self):
        self.active_app: Optional[AppType] = None
        self.active_window = None
        self.pywinauto_app = None
        self.sct = mss.mss() if 'mss' in globals() else None
        pyautogui.FAILSAFE = True  # Emergency stop by moving mouse to corner
        pyautogui.PAUSE = 0.5
        
    # ═══════════════════════════════════════════════════════
    # 1. Launch applications
    # ═══════════════════════════════════════════════════════
    
    def launch_app(self, app_type: AppType, executable_path: Optional[str] = None) -> bool:
        """Launch CAD/BIM application"""
        logger.info(f"Launching {app_type.value}...")
        
        executables = {
            AppType.AUTOCAD: "acad.exe",
            AppType.REVIT: "Revit.exe",
            AppType.ETABS: "ETABS.exe",
        }
        
        exe = executable_path or executables.get(app_type, app_type.value)
        
        try:
            if PYWINAUTO_AVAILABLE:
                self.pywinauto_app = Application().start(exe)
                time.sleep(5)  # Wait for loading
                self.active_window = self.pywinauto_app.top_window()
            else:
                import subprocess
                subprocess.Popen(exe)
                time.sleep(5)
                
            self.active_app = app_type
            logger.info(f"{app_type.value} launched successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch {app_type.value}: {e}")
            return False
    
    def connect_to_running_app(self, app_type: AppType, window_title: str) -> bool:
        """Connect to already running application"""
        try:
            if PYWINAUTO_AVAILABLE:
                self.pywinauto_app = Application().connect(title_re=window_title)
                self.active_window = self.pywinauto_app.window(title_re=window_title)
                self.active_window.set_focus()
                self.active_app = app_type
                return True
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════
    # 2. Screenshot & Vision
    # ═══════════════════════════════════════════════════════
    
    def capture_screen(self, region: Optional[ScreenRegion] = None) -> np.ndarray:
        """Take screenshot"""
        if region:
            monitor = {
                "left": region.x, "top": region.y,
                "width": region.width, "height": region.height
            }
        else:
            monitor = self.sct.monitors[1]  # Primary screen
            
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    
    def capture_to_base64(self, region: Optional[ScreenRegion] = None) -> str:
        """Screenshot as base64 for AI"""
        img = self.capture_screen(region)
        _, buffer = cv2.imencode('.png', img)
        return base64.b64encode(buffer).decode('utf-8')
    
    def find_element_on_screen(self, template_path: str, threshold: float = 0.8) -> Optional[ScreenRegion]:
        """
        Find image (button/element) on screen using Template Matching
        """
        screen = self.capture_screen()
        template = cv2.imread(template_path)
        
        if template is None:
            logger.error(f"Template not found: {template_path}")
            return None
            
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            h, w = template.shape[:2]
            return ScreenRegion(
                x=max_loc[0], y=max_loc[1],
                width=w, height=h
            )
        return None
    
    def find_text_regions(self, text: str) -> List[ScreenRegion]:
        """
        Find text on screen (uses OCR)
        Requires: pip install easyocr
        """
        try:
            import easyocr
            reader = easyocr.Reader(['en', 'ar'])
            img = self.capture_screen()
            results = reader.readtext(img)
            
            regions = []
            for (bbox, detected_text, conf) in results:
                if text.lower() in detected_text.lower():
                    x_coords = [p[0] for p in bbox]
                    y_coords = [p[1] for p in bbox]
                    regions.append(ScreenRegion(
                        x=int(min(x_coords)), y=int(min(y_coords)),
                        width=int(max(x_coords) - min(x_coords)),
                        height=int(max(y_coords) - min(y_coords))
                    ))
            return regions
        except ImportError:
            logger.warning("easyocr not installed. Install with: pip install easyocr")
            return []
    
    # ═══════════════════════════════════════════════════════
    # 3. GUI Automation
    # ═══════════════════════════════════════════════════════
    
    def click(self, region: ScreenRegion, button: str = "left") -> bool:
        """Click on region"""
        x, y = region.center()
        pyautogui.click(x, y, button=button)
        logger.info(f"Clicked at ({x}, {y})")
        return True
    
    def click_by_text(self, text: str, offset: tuple = (0, 0)) -> bool:
        """Find text and click on it"""
        regions = self.find_text_regions(text)
        if regions:
            r = regions[0]
            r.x += offset[0]
            r.y += offset[1]
            self.click(r)
            return True
        logger.warning(f"Text '{text}' not found on screen")
        return False
    
    def click_by_image(self, image_path: str) -> bool:
        """Find image and click on it"""
        region = self.find_element_on_screen(image_path)
        if region:
            self.click(region)
            return True
        return False
    
    def type_text(self, text: str, interval: float = 0.05) -> None:
        """Type text"""
        pyautogui.typewrite(text, interval=interval)
        logger.info(f"Typed: {text}")
    
    def press_key(self, key: str) -> None:
        """Press key"""
        pyautogui.press(key)
        logger.info(f"Pressed: {key}")
    
    def hotkey(self, *keys: str) -> None:
        """Press combination (Ctrl+S, Alt+F4, etc.)"""
        pyautogui.hotkey(*keys)
        logger.info(f"Hotkey: {'+'.join(keys)}")
    
    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """Scroll"""
        pyautogui.scroll(clicks, x, y)
    
    def drag(self, start: tuple, end: tuple, duration: float = 0.5) -> None:
        """Drag from point to point"""
        pyautogui.moveTo(start[0], start[1])
        pyautogui.dragTo(end[0], end[1], duration=duration)
    
    def wait_for_element(self, image_path: str, timeout: float = 30.0, check_interval: float = 1.0) -> Optional[ScreenRegion]:
        """Wait for element to appear on screen"""
        start = time.time()
        while time.time() - start < timeout:
            region = self.find_element_on_screen(image_path)
            if region:
                return region
            time.sleep(check_interval)
        logger.warning(f"Element not found within {timeout}s: {image_path}")
        return None
    
    # ═══════════════════════════════════════════════════════
    # 4. Native CAD/BIM APIs
    # ═══════════════════════════════════════════════════════
    
    def autocad_api_connect(self) -> Optional[Any]:
        """Connect to AutoCAD via COM"""
        if not WIN32_AVAILABLE:
            logger.error("win32com not available")
            return None
            
        try:
            acad = win32com.client.Dispatch("AutoCAD.Application")
            doc = acad.ActiveDocument
            logger.info("Connected to AutoCAD via COM")
            return {"app": acad, "doc": doc}
        except Exception as e:
            logger.error(f"AutoCAD COM connection failed: {e}")
            return None
    
    def revit_api_connect(self) -> Optional[Any]:
        """Connect to Revit via .NET"""
        if not DOTNET_AVAILABLE:
            logger.error("pythonnet not available")
            return None
            
        try:
            clr.AddReference("RevitAPI")
            clr.AddReference("RevitAPIUI")
            from Autodesk.Revit.DB import Document, View, Element, XYZ
            from Autodesk.Revit.UI import UIApplication, UIDocument
            logger.info("Connected to Revit API")
            return {"clr": clr, "revit_types": {"Document": Document, "View": View, "Element": Element, "XYZ": XYZ}}
        except Exception as e:
            logger.error(f"Revit API connection failed: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════
    # 5. AI Workflow Engine
    # ═══════════════════════════════════════════════════════
    
    def execute_ai_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JSON workflow from AI
        
        Example:
        {
            "app": "autocad",
            "steps": [
                {"action": "launch"},
                {"action": "screenshot"},
                {"action": "click_by_text", "params": {"text": "New Drawing"}},
                {"action": "type", "params": {"text": "Project1.dwg"}},
                {"action": "press", "params": {"key": "enter"}},
                {"action": "screenshot"},
                {"action": "analyze", "params": {"query": "Are there any errors?"}}
            ]
        }
        """
        results = []
        screenshots = []
        
        for step in workflow.get("steps", []):
            action = step.get("action")
            params = step.get("params", {})
            
            result = {"action": action, "status": "success", "data": None}
            
            try:
                if action == "launch":
                    app_type = AppType(workflow.get("app", "generic"))
                    self.launch_app(app_type, params.get("path"))
                    
                elif action == "connect":
                    app_type = AppType(workflow.get("app", "generic"))
                    self.connect_to_running_app(app_type, params.get("title", ""))
                    
                elif action == "screenshot":
                    img = self.capture_to_base64()
                    screenshots.append(img)
                    result["data"] = {"screenshot_base64": img[:100] + "..."}
                    
                elif action == "click":
                    region = ScreenRegion(**params)
                    self.click(region)
                    
                elif action == "click_by_text":
                    self.click_by_text(params["text"], params.get("offset", (0, 0)))
                    
                elif action == "click_by_image":
                    self.click_by_image(params["image_path"])
                    
                elif action == "type":
                    self.type_text(params["text"], params.get("interval", 0.05))
                    
                elif action == "press":
                    self.press_key(params["key"])
                    
                elif action == "hotkey":
                    self.hotkey(*params["keys"])
                    
                elif action == "scroll":
                    self.scroll(params["clicks"], params.get("x"), params.get("y"))
                    
                elif action == "drag":
                    self.drag(
                        (params["start_x"], params["start_y"]),
                        (params["end_x"], params["end_y"]),
                        params.get("duration", 0.5)
                    )
                    
                elif action == "wait_for_element":
                    region = self.wait_for_element(
                        params["image_path"],
                        params.get("timeout", 30),
                        params.get("interval", 1)
                    )
                    result["data"] = {"found": region is not None, "region": region}
                    
                elif action == "autocad_api":
                    result["data"] = self.autocad_api_connect()
                    
                elif action == "revit_api":
                    result["data"] = self.revit_api_connect()
                    
                elif action == "sleep":
                    time.sleep(params.get("seconds", 1))
                    
                else:
                    result["status"] = "unknown_action"
                    
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                
            results.append(result)
            
        return {
            "workflow_completed": True,
            "results": results,
            "screenshots_count": len(screenshots),
            "final_screenshot": screenshots[-1] if screenshots else None
        }
    
    # ═══════════════════════════════════════════════════════
    # 6. Helper: AI Analysis Integration
    # ═══════════════════════════════════════════════════════
    
    def get_screen_for_ai(self) -> str:
        """Return screenshot ready for AI (base64)"""
        return self.capture_to_base64()
    
    def describe_screen_to_ai(self, ai_client, prompt: str = "Describe what you see on this CAD/BIM screen") -> str:
        """
        Send screenshot to AI and request analysis
        
        Usage:
        response = controller.describe_screen_to_ai(claude_client, 
            "Are there any errors in the drawing? Suggest a solution")
        """
        screenshot_b64 = self.get_screen_for_ai()
        # Here send to AI API (Claude, GPT, etc.)
        # Example with Claude:
        # response = ai_client.messages.create(
        #     model="claude-sonnet-4-20250514",
        #     max_tokens=4096,
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "text", "text": prompt},
        #             {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}}
        #         ]
        #     }]
        # )
        return screenshot_b64  # Return base64 for processing


# ═══════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════

_controller_instance: Optional[CADBIMController] = None

def get_controller() -> CADBIMController:
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = CADBIMController()
    return _controller_instance