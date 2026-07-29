# CAD/BIM AI Controller Skill

## Overview
This skill enables AI agents to control CAD/BIM applications (AutoCAD, Revit, ETABS) through:
- GUI automation (click, type, hotkeys)
- Computer Vision (screenshot analysis, element detection)
- Native APIs (COM for AutoCAD, .NET for Revit)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  AI Agent (Claude/GPT)                                  │
│  - Understands user problem                             │
│  - Decides necessary steps                              │
└────────────────────┬────────────────────────────────────┘
                     │ JSON Commands
┌────────────────────▼────────────────────────────────────┐
│  CAD/BIM Controller Skill                               │
│  - Translates commands to GUI actions                   │
│  - Manages screenshots and analysis                     │
└────────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼───┐      ┌───▼───┐      ┌───▼───┐
│AutoCAD│      │ Revit │      │ ETABS │
│(COM)  │      │(API)  │      │(GUI)  │
└───────┘      └───────┘      └───────┘
```

## Features

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

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Example
```python
from .agents.skills.cad-bim-controller.controller import get_controller
from .agents.skills.cad-bim-controller.actions import build_workflow

# Initialize controller
controller = get_controller()

# Build workflow
workflow = {
    "app": "autocad",
    "steps": [
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 5}},
        {"action": "screenshot", "params": {}},
        {"action": "click_by_text", "params": {"text": "New Drawing"}},
        {"action": "screenshot", "params": {}}
    ]
}

# Execute workflow
result = controller.execute_ai_workflow(workflow)
print(f"Workflow completed: {result['workflow_completed']}")
```

### Pre-built Workflows
```python
from .agents.skills.cad-bim-controller.actions import (
    autocad_new_drawing_workflow,
    revit_create_wall_workflow,
    etabs_run_analysis_workflow
)

# Use pre-built workflow
workflow = autocad_new_drawing_workflow()
result = controller.execute_ai_workflow(workflow)
```

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

## Safety Features
- `pyautogui.FAILSAFE = True` — Move mouse to corner to abort
- Always screenshot before/after critical actions
- Use wait_for_element instead of fixed sleeps
- Validate coordinates before clicking

## Supported Applications
- **AutoCAD**: COM API + GUI automation
- **Revit**: .NET API + GUI automation  
- **ETABS**: GUI automation with computer vision
- **Generic CAD**: Pure GUI automation

## Requirements
- Windows OS (for COM/.NET APIs)
- Python 3.8+
- Administrative privileges (for some CAD applications)

## Use Cases
1. **Troubleshooting**: AI identifies and fixes CAD/BIM errors
2. **Automation**: Repetitive tasks automated via AI
3. **Integration**: Bridge between different CAD/BIM platforms
4. **Quality Assurance**: Automated checking and validation