# CAD/BIM AI Controller Skill

## Overview
Skill for AI agents to control AutoCAD, Revit, and ETABS through:
- GUI automation (click, type, hotkeys)
- Computer Vision (screenshot analysis, element detection)
- Native APIs (COM for AutoCAD, .NET for Revit)

## Capabilities

### 1. App Control
- `launch(app, path?)` — Open CAD/BIM application
- `connect(app, window_title)` — Connect to running app
- `close()` — Close active application

### 2. Screen Interaction
- `screenshot(region?)` → base64 image
- `click(x, y)` / `click_by_text(text)` / `click_by_image(template_path)`
- `type(text)` / `press(key)` / `hotkey(keys[])`
- `scroll(clicks)` / `drag(start, end)`

### 3. Vision & Analysis
- `find_element(template_path)` — Template matching
- `find_text(text)` — OCR text search
- `detect_errors()` — Detect error dialogs
- `detect_buttons()` — Find clickable buttons
- `analyze_screen(query)` → Send to AI for analysis

### 4. Native APIs
- `autocad_api_connect()` → COM object
- `revit_api_connect()` → .NET API
- Direct model manipulation (bypass GUI)

## Workflow Format

```json
{
  "app": "autocad | revit | etabs",
  "steps": [
    {"action": "launch", "params": {}},
    {"action": "screenshot", "params": {}},
    {"action": "click_by_text", "params": {"text": "OK"}},
    {"action": "type", "params": {"text": "Hello World"}},
    {"action": "hotkey", "params": {"keys": ["ctrl", "s"]}},
    {"action": "analyze_screen", "params": {"query": "Any errors?"}}
  ]
}
```

## Example: AI Troubleshooting ETABS

User: "ETABS gives error when I run analysis"

AI Workflow:
1. Launch ETABS
2. Screenshot → detect error dialog
3. If error: click OK, read error message
4. Open model file
5. Check load cases
6. Run analysis
7. Screenshot result → analyze

## Example: AutoCAD from Sketch

User: "Draw this wall layout" [image]

AI Workflow:
1. Analyze sketch image → extract coordinates
2. Launch AutoCAD
3. New drawing
4. Draw lines at extracted coordinates
5. Screenshot → verify

## Installation

```bash
pip install pyautogui pywinauto Pillow opencv-python mss numpy easyocr
# For AutoCAD: pip install pywin32
# For Revit: pip install pythonnet
```

## Safety
- `pyautogui.FAILSAFE = True` — Move mouse to corner to abort
- Always screenshot before/after critical actions
- Use wait_for_element instead of fixed sleeps
- Validate coordinates before clicking

## Files
- `controller.py` — Main controller
- `vision.py` — Computer vision
- `actions.py` — Action schemas & workflows
- `examples/` — Sample workflows