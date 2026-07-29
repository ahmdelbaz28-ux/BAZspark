"""
CAD/BIM AI Controller Skill Package
"""

try:
    from .actions import (
        ActionType,
        autocad_new_drawing_workflow,
        build_workflow,
        etabs_run_analysis_workflow,
        revit_create_wall_workflow,
    )
    from .controller import CADBIMController, get_controller
    from .vision import DetectedObject, ScreenAnalyzer

    __all__ = [
        'ActionType',
        'CADBIMController',
        'DetectedObject',
        'ScreenAnalyzer',
        'autocad_new_drawing_workflow',
        'build_workflow',
        'etabs_run_analysis_workflow',
        'get_controller',
        'revit_create_wall_workflow'
    ]
except ImportError:
    # Handle direct imports for testing purposes
    from actions import (
        ActionType,
        autocad_new_drawing_workflow,
        build_workflow,
        etabs_run_analysis_workflow,
        revit_create_wall_workflow,
    )
    from controller import CADBIMController, get_controller
    from vision import DetectedObject, ScreenAnalyzer

    __all__ = [
        'ActionType',
        'CADBIMController',
        'DetectedObject',
        'ScreenAnalyzer',
        'autocad_new_drawing_workflow',
        'build_workflow',
        'etabs_run_analysis_workflow',
        'get_controller',
        'revit_create_wall_workflow'
    ]

__version__ = "1.0.0"
__author__ = "Engineering AI Assistant"
