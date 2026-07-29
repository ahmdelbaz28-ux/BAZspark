"""
Practical Example: AI troubleshoots ETABS
=================================
Scenario: User says "ETABS shows error when running analysis"
AI opens the program, takes screenshot, analyzes, fixes the problem
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..controller import get_controller
from ..actions import build_workflow
import json


def ai_fix_etabs_error():
    """
    Complete workflow to fix an error in ETABS
    """
    controller = get_controller()
    
    # AI builds the workflow
    workflow = build_workflow("etabs", [
        # 1. Open ETABS
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 10}},
        
        # 2. Take screenshot and assess
        {"action": "screenshot", "params": {}},
        
        # 3. If there's an error dialog, close it
        # (AI sees the screenshot and decides)
        {"action": "click_by_text", "params": {"text": "OK", "offset": [0, 0]}},
        
        # 4. Open file
        {"action": "hotkey", "params": {"keys": ["ctrl", "o"]}},
        {"action": "sleep", "params": {"seconds": 1}},
        {"action": "type", "params": {"text": "C:\\Projects\\Tower\\tower_model.e2k"}},
        {"action": "press", "params": {"key": "enter"}},
        {"action": "sleep", "params": {"seconds": 5}},
        
        # 5. Run analysis
        {"action": "click_by_text", "params": {"text": "Analyze", "offset": [0, 0]}},
        {"action": "click_by_text", "params": {"text": "Set Load Cases", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 1}},
        {"action": "screenshot", "params": {}},
        
        # 6. Ensure all load cases are selected
        {"action": "click_by_text", "params": {"text": "Select All", "offset": [0, 0]}},
        {"action": "click_by_text", "params": {"text": "OK", "offset": [0, 0]}},
        
        # 7. Run
        {"action": "click_by_text", "params": {"text": "Run Analysis", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 2}},
        
        # 8. Wait for result
        {"action": "wait_for_element", "params": {
            "image_path": "templates/etabs_analysis_done.png",
            "timeout": 180
        }},
        
        # 9. Take screenshot of results
        {"action": "screenshot", "params": {}},
        
        # 10. Analyze results
        {"action": "analyze_screen", "params": {
            "query": "Did the analysis complete? Any warnings or errors? Show me the results."
        }}
    ])
    
    # Execute the workflow
    result = controller.execute_ai_workflow(workflow)
    
    print("=" * 60)
    print("WORKFLOW RESULTS:")
    print("=" * 60)
    for step_result in result["results"]:
        print(f"  {step_result['action']}: {step_result['status']}")
        if 'error' in step_result:
            print(f"    ERROR: {step_result['error']}")
    
    print(f"\nScreenshots captured: {result['screenshots_count']}")
    return result


def ai_create_revit_wall_from_screenshot():
    """
    Scenario: User sends a hand-drawn sketch image
    AI understands it and creates a wall in Revit
    """
    controller = get_controller()
    
    # AI analyzes image and extracts coordinates
    # Then builds workflow
    
    workflow = build_workflow("revit", [
        {"action": "launch", "params": {}},
        {"action": "sleep", "params": {"seconds": 15}},
        
        # New Project
        {"action": "hotkey", "params": {"keys": ["ctrl", "n"]}},
        {"action": "sleep", "params": {"seconds": 3}},
        {"action": "press", "params": {"key": "enter"}},  # Select template
        {"action": "sleep", "params": {"seconds": 5}},
        
        # Go to Architecture tab
        {"action": "click_by_text", "params": {"text": "Architecture", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 1}},
        
        # Click Wall
        {"action": "click_by_text", "params": {"text": "Wall", "offset": [0, 0]}},
        {"action": "sleep", "params": {"seconds": 1}},
        
        # Draw wall (from AI-analyzed coordinates)
        {"action": "drag", "params": {
            "start_x": 500, "start_y": 500,
            "end_x": 1000, "end_y": 500,
            "duration": 0.5
        }},
        {"action": "sleep", "params": {"seconds": 1}},
        
        # Press Escape to finish
        {"action": "press", "params": {"key": "esc"}},
        
        # Screenshot to verify
        {"action": "screenshot", "params": {}},
        {"action": "analyze_screen", "params": {
            "query": "Is the wall created correctly? What are its dimensions?"
        }}
    ])
    
    return controller.execute_ai_workflow(workflow)


if __name__ == "__main__":
    # Choose scenario
    print("1. Fix ETABS Error")
    print("2. Create Revit Wall from Drawing")
    
    choice = input("Choose (1/2): ")
    
    if choice == "1":
        ai_fix_etabs_error()
    elif choice == "2":
        ai_create_revit_wall_from_screenshot()