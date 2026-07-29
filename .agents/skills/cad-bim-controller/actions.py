"""
JSON Actions Schema for CAD/BIM Controller
==========================================
Each action is represented as a JSON object the AI can send
"""

from typing import TypedDict, Optional, List, Union
from enum import Enum


class ActionType(Enum):
    # App Control
    LAUNCH = "launch"
    CONNECT = "connect"
    CLOSE = "close"
    
    # Navigation
    SCREENSHOT = "screenshot"
    CLICK = "click"
    CLICK_BY_TEXT = "click_by_text"
    CLICK_BY_IMAGE = "click_by_image"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    
    # Input
    TYPE = "type"
    PRESS = "press"
    HOTKEY = "hotkey"
    
    # Mouse
    SCROLL = "scroll"
    DRAG = "drag"
    MOVE_TO = "move_to"
    
    # Wait
    WAIT = "wait"
    WAIT_FOR_ELEMENT = "wait_for_element"
    SLEEP = "sleep"
    
    # API
    AUTOCAD_API = "autocad_api"
    REVIT_API = "revit_api"
    ETABS_API = "etabs_api"
    
    # Analysis
    ANALYZE_SCREEN = "analyze_screen"
    FIND_TEXT = "find_text"
    FIND_ELEMENT = "find_element"


# ═══════════════════════════════════════════════════════
# Action Schemas (for AI to understand)
# ═══════════════════════════════════════════════════════

LAUNCH_SCHEMA = {
    "action": "launch",
    "params": {
        "app": "autocad | revit | etabs | generic",
        "path": "optional: full path to executable"
    }
}

SCREENSHOT_SCHEMA = {
    "action": "screenshot",
    "params": {
        "region": {"x": 0, "y": 0, "width": 1920, "height": 1080}  # optional
    }
}

CLICK_BY_TEXT_SCHEMA = {
    "action": "click_by_text",
    "params": {
        "text": "Button text to find",
        "offset": [0, 0]  # optional offset from found text
    }
}

CLICK_BY_IMAGE_SCHEMA = {
    "action": "click_by_image",
    "params": {
        "image_path": "path/to/button_template.png",
        "confidence": 0.8
    }
}

TYPE_SCHEMA = {
    "action": "type",
    "params": {
        "text": "text to type",
        "interval": 0.05  # typing speed
    }
}

HOTKEY_SCHEMA = {
    "action": "hotkey",
    "params": {
        "keys": ["ctrl", "s"]  # or ["alt", "f4"], etc.
    }
}

WAIT_FOR_ELEMENT_SCHEMA = {
    "action": "wait_for_element",
    "params": {
        "image_path": "path/to/element.png",
        "timeout": 30,
        "check_interval": 1
    }
}

ANALYZE_SCREEN_SCHEMA = {
    "action": "analyze_screen",
    "params": {
        "query": "What do you see? Any errors?"
    }
}


# ═══════════════════════════════════════════════════════
# Helper: Build workflows
# ═══════════════════════════════════════════════════════

def build_workflow(app: str, steps: List[dict]) -> dict:
    """Build workflow JSON"""
    return {
        "app": app,
        "steps": steps
    }


# Pre-built examples for AI

def autocad_new_drawing_workflow() -> dict:
    """Open AutoCAD and create New Drawing"""
    return build_workflow("autocad", [
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 5}},
        {"action": "screenshot", "params": {}},
        {"action": "click_by_text", "params": {"text": "New", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 1}},
        {"action": "click_by_text", "params": {"text": "Drawing", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 2}},
        {"action": "screenshot", "params": {}},
        {"action": "analyze_screen", "params": {"query": "Is the new drawing open? Any errors?"}}
    ])


def revit_create_wall_workflow() -> dict:
    """Create Wall in Revit"""
    return build_workflow("revit", [
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 10}},
        {"action": "screenshot", "params": {}},
        {"action": "click_by_text", "params": {"text": "Architecture", "offset": [0, 0]}},
        {"action": "click_by_text", "params": {"text": "Wall", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 1}},
        {"action": "type", "params": {"text": "Level 1"}},
        {"action": "press", "params": {"key": "enter"}},
        {"action": "screenshot", "params": {}}
    ])


def etabs_run_analysis_workflow() -> dict:
    """Run Analysis in ETABS"""
    return build_workflow("etabs", [
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 8}},
        {"action": "hotkey", "params": {"keys": ["ctrl", "o"]}},
        {"action": "sleep", "params": {"seconds": 1}},
        {"action": "type", "params": {"text": "C:\\Models\\building.e2k"}},
        {"action": "press", "params": {"key": "enter"}},
        {"action": "sleep", "params": {"seconds": 3}},
        {"action": "click_by_text", "params": {"text": "Analyze", "offset": [0, 0]}},
        {"action": "click_by_text", "params": {"text": "Run Analysis", "offset": [0, 0]}},
        {"action": "wait_for_element", "params": {
            "image_path": "templates/analysis_complete.png",
            "timeout": 120
        }},
        {"action": "screenshot", "params": {}},
        {"action": "analyze_screen", "params": {"query": "Did the analysis complete successfully? Any warnings?"}}
    ])