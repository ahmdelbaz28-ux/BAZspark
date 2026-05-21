"""
fireai/bridges — BIM Integration Bridges for FireAI
=====================================================
Headless bridges for reading/writing building data without
requiring active GUI applications (Revit, AutoCAD, etc.).
"""
from fireai.bridges.ifc_headless_bridge import HeadlessIFCBridge

__all__ = ["HeadlessIFCBridge"]
