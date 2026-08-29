"""
backend/core/constants.py — Project-wide string and configuration constants.
=============================================================================
Centralizes repeated string constants across providers, routers, and engines
to maintain single-source-of-truth and eliminate code smells (Sonar python:S1192).
"""

# ── LLM & AI Provider Base URLs ──────────────────────────────────────────────
GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
OPENAI_BASE_URL: str = "https://api.openai.com/v1"
XAI_BASE_URL: str = "https://api.x.ai/v1"
MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
OLLAMA_DEFAULT_BASE_URL: str = "http://localhost:11434"

# ── Default LLM Models ────────────────────────────────────────────────────────
DEFAULT_GEMINI_MODEL: str = "gemini-2.0-flash"
DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
DEFAULT_OPENAI_MODEL: str = "gpt-4o"
DEFAULT_GROQ_MODEL: str = "llama-3.3-70b-versatile"
DEFAULT_DEEPSEEK_MODEL: str = "deepseek-chat"
DEFAULT_MISTRAL_MODEL: str = "mistral-large-latest"

# ── Export & File Formats ─────────────────────────────────────────────────────
EXPORT_FORMAT_JSON: str = ".json"
EXPORT_FORMAT_DXF: str = ".dxf"
EXPORT_FORMAT_DWG: str = ".dwg"
EXPORT_FORMAT_IFC: str = ".ifc"
EXPORT_FORMAT_CSV: str = ".csv"
EXPORT_FORMAT_XLSX: str = ".xlsx"
EXPORT_FORMAT_PDF: str = ".pdf"
EXPORT_FORMAT_RVT: str = ".rvt"

SUPPORTED_EXPORT_FORMATS_DESC: str = "Target format: dxf, revit, ifc, xlsx, csv, json, pdf"
