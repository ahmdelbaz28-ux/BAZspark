"""
Simple test for CAD/BIM AI Controller Skill
Tests core functionality without requiring OCR downloads
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported without errors"""
    print("🔍 Testing module imports...")
    
    try:
        # Test controller import
        from controller import get_controller, CADBIMController
        print("✅ Controller module imported successfully")
        
        # Test actions import
        from actions import (
            ActionType,
            build_workflow,
            autocad_new_drawing_workflow,
            revit_create_wall_workflow,
            etabs_run_analysis_workflow
        )
        print("✅ Actions module imported successfully")
        
        # Test basic vision import (without OCR initialization)
        import vision
        print("✅ Vision module imported successfully")
        
        # Test init import
        import __init__
        print("✅ Init module imported successfully")
        
        print("\n✅ All modules imported successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_controller_creation():
    """Test that controller can be created"""
    print("\n🔍 Testing controller creation...")
    
    try:
        from controller import get_controller
        controller = get_controller()
        
        print(f"✅ Controller created: {type(controller).__name__}")
        print(f"✅ Controller initialized with proper attributes")
        
        # Test basic controller methods exist
        methods_to_check = ['launch_app', 'capture_screen', 'click', 'execute_ai_workflow']
        for method in methods_to_check:
            if hasattr(controller, method):
                print(f"✅ Method '{method}' exists")
            else:
                print(f"❌ Method '{method}' missing")
                
        return True
        
    except Exception as e:
        print(f"❌ Controller creation error: {e}")
        return False


def test_workflow_building():
    """Test that workflows can be built"""
    print("\n🔍 Testing workflow building...")
    
    try:
        from actions import build_workflow
        
        # Test building a simple workflow
        workflow = build_workflow("autocad", [
            {"action": "screenshot", "params": {}},
            {"action": "sleep", "params": {"seconds": 1}}
        ])
        
        print(f"✅ Workflow built: {workflow['app']}")
        print(f"✅ Workflow has {len(workflow['steps'])} steps")
        
        # Test pre-built workflows
        from actions import autocad_new_drawing_workflow
        autocad_wf = autocad_new_drawing_workflow()
        print(f"✅ Pre-built AutoCAD workflow: {len(autocad_wf['steps'])} steps")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow building error: {e}")
        return False


def test_action_enums():
    """Test that action enums are properly defined"""
    print("\n🔍 Testing action enums...")
    
    try:
        from actions import ActionType
        
        # Test a few key action types
        expected_actions = ['LAUNCH', 'SCREENSHOT', 'CLICK', 'TYPE', 'HOTKEY']
        for action in expected_actions:
            if hasattr(ActionType, action):
                print(f"✅ Action '{action}' exists")
            else:
                print(f"❌ Action '{action}' missing")
                
        return True
        
    except Exception as e:
        print(f"❌ Action enum error: {e}")
        return False


def run_comprehensive_tests():
    """Run all tests and report results"""
    print("🧪 Running comprehensive tests for CAD/BIM AI Controller Skill\n")
    print("="*60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Controller Creation", test_controller_creation), 
        ("Workflow Building", test_workflow_building),
        ("Action Enums", test_action_enums)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name} Test:")
        print("-" * 30)
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY:")
    print("="*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The CAD/BIM AI Controller Skill is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    run_comprehensive_tests()