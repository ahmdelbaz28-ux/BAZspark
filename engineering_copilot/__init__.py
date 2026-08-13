"""
ETAP-AI-WORK Engineering Copilot - Main Module
============================================

Principal Software Architect: Eng. Ahmed Elbaz
Lead Solution Architect: Eng. Ahmed Elbaz
Principal Autodesk Integration Engineer: Eng. Ahmed Elbaz
"""
from .ai_agent.ai_agent import AICopilot, EngineeringIntentProcessor
from .connectors.autocad_connector import AutoCADConnector
from .connectors.etap_connector import ETAPConnector
from .connectors.revit_connector import RevitConnector
from .mcp_server.mcp_server import get_mcp_app, mcp_server
from .models import (
    Annotation,
    BaseEntity,
    Breaker,
    Building,
    Bus,
    Cable,
    Conduit,
    Coordinates,
    ElectricalRoom,
    Equipment,
    Generator,
    Level,
    Load,
    Motor,
    Panel,
    Project,
    ProtectionDevice,
    Relay,
    Room,
    Switchboard,
    Transformer,
    Tray,
    UnifiedEngineeringModel,
)
from .translation_engine.translation_engine import TranslationEngine

__version__ = "1.0.0"
__author__ = "Eng. Ahmed Elbaz"
__all__ = [
    # AI Agent
    'AICopilot',
    'Annotation',
    # Connectors
    'AutoCADConnector',
    # Models
    'BaseEntity',
    'Breaker',
    'Building',
    'Bus',
    'Cable',
    'Conduit',
    'Coordinates',
    'ETAPConnector',
    'ElectricalRoom',
    'EngineeringIntentProcessor',
    'Equipment',
    'Generator',
    'Level',
    'Load',
    'Motor',
    'Panel',
    'Project',
    'ProtectionDevice',
    'Relay',
    'RevitConnector',
    'Room',
    'Switchboard',
    'Transformer',
    # Translation Engine
    'TranslationEngine',
    'Tray',
    'UnifiedEngineeringModel',
    'get_mcp_app',
    # MCP Server
    'mcp_server'
]
