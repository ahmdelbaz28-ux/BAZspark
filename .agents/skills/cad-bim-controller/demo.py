"""
Demo script for CAD/BIM AI Controller Skill
Shows how to use the skill to control CAD/BIM applications
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controller import get_controller
from actions import build_workflow, autocad_new_drawing_workflow
from vision import ScreenAnalyzer


def demo_basic_usage():
    """Demonstrate basic usage of the CAD/BIM controller"""
    print("🔧 Initializing CAD/BIM AI Controller...")
    
    # Get the controller instance
    controller = get_controller()
    print("✅ Controller initialized successfully!")
    
    # Example: Build a simple workflow
    print("\n📝 Building a simple workflow...")
    simple_workflow = build_workflow("generic", [
        {"action": "screenshot", "params": {}},
        {"action": "sleep", "params": {"seconds": 1}}
    ])
    
    print("✅ Workflow built successfully!")
    print(f"   Workflow has {len(simple_workflow['steps'])} steps")
    
    # Example: Initialize the vision analyzer
    print("\n🔍 Initializing vision analyzer...")
    try:
        analyzer = ScreenAnalyzer()
        print("✅ Vision analyzer initialized successfully!")
    except Exception as e:
        print(f"⚠️ Vision analyzer initialization issue: {e}")
    
    print("\n🎯 CAD/BIM AI Controller Skill is ready to use!")
    print("\n💡 Example usage:")
    print("   controller = get_controller()")
    print("   workflow = build_workflow('autocad', [...])")
    print("   result = controller.execute_ai_workflow(workflow)")
    print("\n📋 Available actions:")
    print("   - launch, connect, screenshot")
    print("   - click, click_by_text, click_by_image")
    print("   - type, press, hotkey")
    print("   - scroll, drag, sleep")
    print("   - autocad_api, revit_api, analyze_screen")


def demo_sample_workflows():
    """Show some pre-built workflows"""
    print("\n🏗️  Pre-built workflows available:")
    
    # AutoCAD workflow
    autocad_wf = autocad_new_drawing_workflow()
    print(f"   ✅ AutoCAD: {len(autocad_wf['steps'])} steps for creating new drawing")
    
    print("\n📊 Workflow example:")
    print("   {")
    print('       "app": "autocad",')
    print('       "steps": [')
    for i, step in enumerate(autocad_wf['steps'][:3]):  # Show first 3 steps
        print(f'           {step}{"," if i < 2 else ""}')
    print('           ...')
    print('       ]')
    print("   }")


if __name__ == "__main__":
    print("🏗️  CAD/BIM AI Controller Skill - Demo")
    print("=" * 50)
    
    demo_basic_usage()
    demo_sample_workflows()
    
    print("\n" + "=" * 50)
    print("🎉 Demo completed successfully!")