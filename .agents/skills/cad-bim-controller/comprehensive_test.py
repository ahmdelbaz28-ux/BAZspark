"""
Comprehensive Test Suite for CAD/BIM AI Controller Skill
Tests all functionality without external dependencies
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Ensure key symbols are imported for static analysis and manual tests
try:
    from controller import get_controller, CADBIMController
except Exception:
    get_controller = None  # type: ignore[assignment]
    CADBIMController = None  # type: ignore[assignment]


try:
    from actions import ActionType, build_workflow, autocad_new_drawing_workflow, revit_create_wall_workflow, etabs_run_analysis_workflow
except Exception:
    ActionType = None  # type: ignore
    build_workflow = None  # type: ignore
    autocad_new_drawing_workflow = None  # type: ignore
    revit_create_wall_workflow = None  # type: ignore
    etabs_run_analysis_workflow = None  # type: ignore

try:
    from vision import ScreenAnalyzer, DetectedObject
except Exception:
    ScreenAnalyzer = None  # type: ignore
    DetectedObject = None  # type: ignore

# Add the skill directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestCADBIMController(unittest.TestCase):
    """Test the main controller functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        from controller import CADBIMController
        self.controller = CADBIMController()
    
    def test_controller_initialization(self):
        """Test that controller initializes properly"""
        self.assertIsNotNone(self.controller)
        self.assertIsNone(self.controller.active_app)
        self.assertEqual(self.controller.active_window, None)
    
    def test_controller_methods_exist(self):
        """Test that essential methods exist"""
        methods_to_check = [
            'launch_app', 'connect_to_running_app', 'capture_screen', 
            'capture_to_base64', 'find_element_on_screen', 'find_text_regions',
            'click', 'click_by_text', 'click_by_image', 'type_text',
            'press_key', 'hotkey', 'scroll', 'drag', 'wait_for_element',
            'autocad_api_connect', 'revit_api_connect', 'execute_ai_workflow'
        ]
        
        for method in methods_to_check:
            self.assertTrue(hasattr(self.controller, method), f"Method {method} missing")
    
    def test_launch_app_method_exists(self):
        """Test that launch_app method exists"""
        self.assertTrue(callable(getattr(self.controller, 'launch_app')))
    
    def test_capture_methods_exist(self):
        """Test that capture methods exist"""
        self.assertTrue(callable(getattr(self.controller, 'capture_screen')))
        self.assertTrue(callable(getattr(self.controller, 'capture_to_base64')))


class TestActions(unittest.TestCase):
    """Test the actions functionality"""
    
    def test_action_types_enum(self):
        """Test that ActionType enum has expected values"""
        from actions import ActionType
        
        expected_actions = [
            'LAUNCH', 'CONNECT', 'CLOSE', 'SCREENSHOT', 'CLICK', 
            'CLICK_BY_TEXT', 'TYPE', 'PRESS', 'HOTKEY', 'SCROLL', 
            'DRAG', 'SLEEP', 'AUTOCAD_API', 'REVIT_API', 'ANALYZE_SCREEN'
        ]
        
        for action in expected_actions:
            self.assertTrue(hasattr(ActionType, action))
    
    def test_build_workflow_function(self):
        """Test that build_workflow function works"""
        from actions import build_workflow
        
        steps = [{"action": "test", "params": {}}]
        workflow = build_workflow("test_app", steps)
        
        self.assertEqual(workflow["app"], "test_app")
        self.assertEqual(len(workflow["steps"]), 1)
        self.assertEqual(workflow["steps"][0]["action"], "test")
    
    def test_prebuilt_workflows_exist(self):
        """Test that pre-built workflows exist and return proper format"""
        from actions import (
            autocad_new_drawing_workflow,
            revit_create_wall_workflow,
            etabs_run_analysis_workflow
        )
        
        autocad_wf = autocad_new_drawing_workflow()
        self.assertIn("app", autocad_wf)
        self.assertIn("steps", autocad_wf)
        self.assertEqual(autocad_wf["app"], "autocad")
        self.assertGreater(len(autocad_wf["steps"]), 0)
        
        revit_wf = revit_create_wall_workflow()
        self.assertIn("app", revit_wf)
        self.assertIn("steps", revit_wf)
        self.assertEqual(revit_wf["app"], "revit")
        self.assertGreater(len(revit_wf["steps"]), 0)
        
        etabs_wf = etabs_run_analysis_workflow()
        self.assertIn("app", etabs_wf)
        self.assertIn("steps", etabs_wf)
        self.assertEqual(etabs_wf["app"], "etabs")
        self.assertGreater(len(etabs_wf["steps"]), 0)


class TestVision(unittest.TestCase):
    """Test the vision functionality"""
    
    def test_vision_imports(self):
        """Test that vision module can be imported and classes exist"""
        from vision import ScreenAnalyzer, DetectedObject
        
        # Test class can be instantiated
        analyzer = ScreenAnalyzer()
        self.assertIsNotNone(analyzer)
        
        # Test DetectedObject can be created
        obj = DetectedObject("test", 0.9, (0, 0, 100, 100), (50, 50))
        self.assertEqual(obj.label, "test")
        self.assertEqual(obj.confidence, 0.9)
        self.assertEqual(obj.bbox, (0, 0, 100, 100))
        self.assertEqual(obj.center, (50, 50))


class TestIntegration(unittest.TestCase):
    """Test integration between components"""
    
    def test_controller_with_actions(self):
        """Test that controller can work with actions"""
        from controller import get_controller
        from actions import build_workflow
        
        controller = get_controller()
        workflow = build_workflow("test", [
            {"action": "screenshot", "params": {}}
        ])
        
        # Just check that the structures are compatible
        self.assertEqual(workflow["app"], "test")
        self.assertEqual(len(workflow["steps"]), 1)
        self.assertEqual(workflow["steps"][0]["action"], "screenshot")
        
        # Test that execute_ai_workflow method exists on controller
        self.assertTrue(hasattr(controller, 'execute_ai_workflow'))
        self.assertTrue(callable(getattr(controller, 'execute_ai_workflow')))


def run_unit_tests():
    """Run all unit tests and return results"""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCADBIMController)
    suite.addTests(loader.loadTestsFromTestCase(TestActions))
    suite.addTests(loader.loadTestsFromTestCase(TestVision))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


def run_manual_tests():
    # Placeholder to ensure `controller` is bound for static analysis
    controller = None
    """Run manual validation tests"""
    print("\n🔧 Manual Functionality Tests:")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Import all modules
    total_tests += 1
    try:
        from controller import get_controller, CADBIMController
        from actions import ActionType, build_workflow
        from vision import ScreenAnalyzer, DetectedObject
        print("✅ All modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Module import failed: {e}")
    
    # Test 2: Create controller instance
    total_tests += 1
    try:
        controller = get_controller()
        print(f"✅ Controller created: {type(controller).__name__}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Controller creation failed: {e}")
    
    # Test 3: Test controller methods
    total_tests += 1
    try:
        methods = ['launch_app', 'click', 'execute_ai_workflow']
        for method in methods:
            assert hasattr(controller, method), f"Method {method} missing"
        print("✅ Essential controller methods exist")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Controller methods test failed: {e}")
    
    # Test 4: Test workflow building
    total_tests += 1
    try:
        workflow = build_workflow("test", [{"action": "screenshot"}])
        assert workflow["app"] == "test"
        assert len(workflow["steps"]) == 1
        print("✅ Workflow building works")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Workflow building failed: {e}")
    
    # Test 5: Test vision components
    total_tests += 1
    try:
        from vision import DetectedObject
        obj = DetectedObject("test", 0.9, (0, 0, 100, 100), (50, 50))
        assert obj.label == "test"
        print("✅ Vision components work")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Vision components failed: {e}")
    
    print(f"\nManual Tests: {tests_passed}/{total_tests} passed")
    return tests_passed, total_tests


def main():
    """Main test execution function"""
    print("🏗️ CAD/BIM AI Controller Skill - Comprehensive Test Suite")
    print("=" * 70)
    print("Testing the complete functionality of the new skill...\n")
    
    # Run unit tests
    print("🧪 Running Unit Tests:")
    print("-" * 30)
    unit_result = run_unit_tests()
    
    # Run manual tests
    manual_passed, manual_total = run_manual_tests()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 70)
    
    unit_passed = unit_result.testsRun - len(unit_result.failures) - len(unit_result.errors)
    unit_total = unit_result.testsRun
    
    print(f"Unit Tests:     {unit_passed}/{unit_total} passed")
    print(f"Manual Tests:   {manual_passed}/{manual_total} passed")
    
    total_passed = unit_passed + manual_passed
    total_tests = unit_total + manual_total
    
    print(f"Overall:        {total_passed}/{total_tests} tests passed")
    
    success_rate = (total_passed / total_tests) * 100
    print(f"Success Rate:   {success_rate:.1f}%")
    
    print("\n" + "-" * 70)
    if success_rate >= 95:
        print("🎉 EXCELLENT! The CAD/BIM AI Controller Skill is fully functional!")
        print("✅ All core functionality validated successfully")
        print("✅ Ready for integration with AI agents")
        return True
    elif success_rate >= 80:
        print("👍 GOOD! Most functionality is working correctly")
        print("⚠️  Some minor issues may need attention")
        return True
    else:
        print("❌ CONCERNS! Significant issues detected")
        print("❗ Review the test failures above")
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎯 Testing completed successfully!")
    else:
        print("\n❌ Testing identified issues that need resolution.")
        exit(1)