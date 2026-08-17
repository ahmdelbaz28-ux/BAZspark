"""
backend/routers/audio.py - Hardened Voice & Audio Processing Router.
====================================================================
Provides secure endpoints for:
  - Audio file upload and transcription with strict MIME & size validation
  - Voice transcribed prompt sanitization and prompt-injection defense
  - Rate limiting and JWT role-based access control (RBAC)
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Final

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.limiter import limiter
from backend.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio"])

# Allowed audio MIME types for upload
ALLOWED_AUDIO_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "audio/webm",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/ogg",
        "audio/mp4",
        "audio/mpeg",
        "audio/mp3",
        "audio/aac",
        "audio/flac",
    }
)

MAX_AUDIO_SIZE_BYTES: Final[int] = 10 * 1024 * 1024

# Prompt injection and jailbreak patterns to defang/filter
PROMPT_INJECTION_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b"),
    re.compile(r"(?i)\bsystem\s+prompt\b"),
    re.compile(r"(?i)\byou\s+are\s+now\b"),
    re.compile(r"(?i)\bdeveloper\s+mode\b"),
    re.compile(r"(?i)\bjailbreak\b"),
    re.compile(r"(?i)\boverride\s+safety\s+guidelines\b"),
]


def sanitize_transcribed_text(raw_text: str) -> str:
    """
    Sanitizes voice-transcribed input to prevent prompt injection attacks,
    strips non-printable control characters, and normalizes whitespace.
    """
    if not raw_text:
        return ""

    # 1. Remove non-printable control characters (except common whitespace)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", raw_text)

    # 2. Neutralize code injection and template formatting markers
    cleaned = cleaned.replace("`", "'").replace("${", "{").replace("}}", "} ")

    # 3. Filter prompt injection attempts
    for pat in PROMPT_INJECTION_PATTERNS:
        cleaned = pat.sub("[FILTERED]", cleaned)

    # 4. Normalize multi-whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


class SanitizeRequest(BaseModel):
    """Payload for text sanitization."""

    text: str = Field(..., max_length=10000, description="Raw transcribed voice text to sanitize")


class SanitizeResponse(BaseModel):
    """Sanitized voice output response."""

    success: bool = True
    sanitized_text: str
    original_length: int
    sanitized_length: int


class TranscribeResponse(BaseModel):
    """Audio transcription response."""

    success: bool = True
    text: str
    filename: str
    content_type: str
    size_bytes: int
    duration_seconds: float | None = None
    language: str = "en-US"


@router.post(
    "/sanitize",
    dependencies=[Depends(require_permission(Permission.CALCULATION_READ))],
)
@limiter.limit("60/minute")
async def sanitize_voice_text(
    request: Request,
    body: SanitizeRequest,
) -> SanitizeResponse:
    """
    Sanitizes voice transcribed text before submission into LLM/AI execution pipelines.
    """
    sanitized = sanitize_transcribed_text(body.text)
    return SanitizeResponse(
        success=True,
        sanitized_text=sanitized,
        original_length=len(body.text),
        sanitized_length=len(sanitized),
    )


@router.post(
    "/transcribe",
    dependencies=[Depends(require_permission(Permission.CALCULATION_READ))],
)
@limiter.limit("20/minute")
async def transcribe_audio_file(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    language: Annotated[str, Form()] = "auto",
) -> TranscribeResponse:
    """
    Accepts and validates audio recordings for speech-to-text processing.

    Enforces:
      - Valid audio MIME types (audio/webm, audio/wav, audio/ogg, etc.)
      - Max file size limit <= 10MB
      - JWT role-based authorization
    """
    raw_content_type = (file.content_type or "").lower().split(";")[0].strip()

    if raw_content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported audio MIME type '{file.content_type}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_AUDIO_MIME_TYPES))}"
            ),
        )

    # Validate size up to MAX_AUDIO_SIZE_BYTES
    contents = await file.read(MAX_AUDIO_SIZE_BYTES + 1)
    if len(contents) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds maximum allowed size of 10MB.",
        )

    clean_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename or "audio_recording")[:128]

    # For development/pipeline stub: return empty clean transcript or processed text
    sanitized_output = sanitize_transcribed_text("")

    if language.startswith("ar"):
        resolved_language = "ar-EG"
    elif language != "auto":
        resolved_language = "en-US"
    else:
        resolved_language = "auto"

    return TranscribeResponse(
        success=True,
        text=sanitized_output,
        filename=clean_filename,
        content_type=raw_content_type,
        size_bytes=len(contents),
        duration_seconds=None,
        language=resolved_language,
    )
