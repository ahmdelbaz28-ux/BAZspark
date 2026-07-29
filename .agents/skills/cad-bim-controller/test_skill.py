"""
Test script to verify CAD/BIM AI Controller Skill
"""

def test_imports():
    """Test that all modules can be imported without errors"""
    try:
        from controller import get_controller, CADBIMController
        print("✓ Controller module imported successfully")
        
        from actions import (
            ActionType,
            build_workflow,
            autocad_new_drawing_workflow,
            revit_create_wall_workflow,
            etabs_run_analysis_workflow
        )
        print("✓ Actions module imported successfully")
        
        from vision import ScreenAnalyzer, DetectedObject
        print("✓ Vision module imported successfully")
        
        import __init__
        print("✓ Init module imported successfully")
        
        print("\n✓ All modules imported successfully!")
        print("CAD/BIM AI Controller Skill is ready to use.")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_imports()