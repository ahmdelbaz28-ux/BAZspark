"""
CAD/BIM AI Controller Skill Package
"""

try:
    from .controller import get_controller, CADBIMController
    from .actions import (
        ActionType,
        build_workflow,
        autocad_new_drawing_workflow,
        revit_create_wall_workflow,
        etabs_run_analysis_workflow
    )
    from .vision import ScreenAnalyzer, DetectedObject
    
    __all__ = [
        'get_controller',
        'CADBIMController',
        'ScreenAnalyzer',
        'DetectedObject',
        'ActionType',
        'build_workflow',
        'autocad_new_drawing_workflow',
        'revit_create_wall_workflow',
        'etabs_run_analysis_workflow'
    ]
except ImportError:
    # Handle direct imports for testing purposes
    from controller import get_controller, CADBIMController
    from actions import (
        ActionType,
        build_workflow,
        autocad_new_drawing_workflow,
        revit_create_wall_workflow,
        etabs_run_analysis_workflow
    )
    from vision import ScreenAnalyzer, DetectedObject
    
    __all__ = [
        'get_controller',
        'CADBIMController',
        'ScreenAnalyzer',
        'DetectedObject',
        'ActionType',
        'build_workflow',
        'autocad_new_drawing_workflow',
        'revit_create_wall_workflow',
        'etabs_run_analysis_workflow'
    ]

__version__ = "1.0.0"
__author__ = "Engineering AI Assistant"