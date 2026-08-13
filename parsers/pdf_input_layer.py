# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
FIREAI PDF INPUT LAYER — Real Drawing Parser
=====================================
"""

import logging
import os
import re
from dataclasses import dataclass, field

from parsers._device_types import DeviceType
from parsers.parser_confidence import ConfidenceResult, GateDecision, ParserConfidence

logger = logging.getLogger("fireai.input_layer")


# ═══════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════

class InputDeviceType(DeviceType):
    NOTIFICATION_APPLIANCE = "NOTIFICATION_APPLIANCE"
    FIRE_ALARM_PANEL = "FIRE_ALARM_PANEL"
    POWER_SUPPLY = "POWER_SUPPLY"
    BATTERY = "BATTERY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractedDevice:
    """Device extracted from PDF with real coordinates."""

    device_type: InputDeviceType
    x: float
    y: float
    page: int
    room: str | None = None
    zone: str | None = None
    elevation: float | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "type": self.device_type.value,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "page": self.page,
            "room": self.room,
            "zone": self.zone,
            "elevation": self.elevation,
            "confidence": self.confidence
        }


@dataclass
class RoomBoundary:
    """Room extracted from floor plan."""

    name: str
    area_sqft: float
    center_x: float
    center_y: float
    ceiling_height: float = 9.0
    boundary_points: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "area_sqft": round(self.area_sqft, 2),
            "center_x": round(self.center_x, 2),
            "center_y": round(self.center_y, 2),
            "ceiling_height": self.ceiling_height,
            "boundary_points": [(round(x, 2), round(y, 2)) for x, y in self.boundary_points]
        }


@dataclass
class DrawingMetadata:
    """Metadata extracted from drawing."""

    building_name: str | None = None
    floor_level: str | None = None
    drawing_scale: str | None = None
    date: str | None = None
    designer: str | None = None
    revision: str | None = None
    north_arrow: bool = False

    def to_dict(self) -> dict:
        return {
            "building_name": self.building_name,
            "floor_level": self.floor_level,
            "drawing_scale": self.drawing_scale,
            "date": self.date,
            "designer": self.designer,
            "revision": self.revision,
            "north_arrow": self.north_arrow
        }


@dataclass
class InputLayerResult:
    """Result of input layer processing."""

    source_pdf: str
    confidence_result: ConfidenceResult
    devices: list[ExtractedDevice] = field(default_factory=list)
    rooms: list[RoomBoundary] = field(default_factory=list)
    metadata: DrawingMetadata | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_accepted(self) -> bool:
        return self.confidence_result.gate != GateDecision.REJECT

    @property
    def device_count(self) -> int:
        return len(self.devices)

    @property
    def room_count(self) -> int:
        return len(self.rooms)

    def to_engine_input(self) -> dict:
        return {
            "source_pdf": self.source_pdf,
            "accepted": self.is_accepted,
            "confidence": {
                "score": self.confidence_result.score,
                "gate": self.confidence_result.gate.value,
                "message": self.confidence_result.message
            },
            "devices": [d.to_dict() for d in self.devices],
            "rooms": [r.to_dict() for r in self.rooms],
            "metadata": self.metadata.to_dict() if self.metadata else {},
            "errors": self.errors,
            "warnings": self.warnings
        }


# ═══════════════════════════════════════════════════════
# NFPA 170 SYMBOL DEFINITIONS
# ═══════════════════════════════════════════════════════

NFPA_170_SYMBOLS = {
    "smoke": InputDeviceType.SMOKE_DETECTOR,
    "sd": InputDeviceType.SMOKE_DETECTOR,
    "smoke detector": InputDeviceType.SMOKE_DETECTOR,
    "heat": InputDeviceType.HEAT_DETECTOR,
    "hd": InputDeviceType.HEAT_DETECTOR,
    "heat detector": InputDeviceType.HEAT_DETECTOR,
    "rate-of-rise": InputDeviceType.HEAT_DETECTOR,
    "fixed temp": InputDeviceType.HEAT_DETECTOR,
    "pull": InputDeviceType.MANUAL_PULL_STATION,
    "ps": InputDeviceType.MANUAL_PULL_STATION,
    "pull station": InputDeviceType.MANUAL_PULL_STATION,
    "manual pull": InputDeviceType.MANUAL_PULL_STATION,
    "break glass": InputDeviceType.MANUAL_PULL_STATION,
    "horn": InputDeviceType.HORN,
    "strobe": InputDeviceType.STROBE,
    "hs": InputDeviceType.HORN_STROBE,
    "horn/strobe": InputDeviceType.HORN_STROBE,
    "horn strobe": InputDeviceType.HORN_STROBE,
    "speaker": InputDeviceType.SPEAKER,
    "bell": InputDeviceType.BELL,
    "fap": InputDeviceType.FIRE_ALARM_PANEL,
    "panel": InputDeviceType.FIRE_ALARM_PANEL,
    "facp": InputDeviceType.FIRE_ALARM_PANEL,
    "fire alarm panel": InputDeviceType.FIRE_ALARM_PANEL,
    "control panel": InputDeviceType.FIRE_ALARM_PANEL,
    "power": InputDeviceType.POWER_SUPPLY,
    "battery": InputDeviceType.BATTERY,
    "sprinkler": InputDeviceType.SPRINKLER,
    "flow switch": InputDeviceType.FLOW_SWITCH,
    "tamper": InputDeviceType.TAMPER_SWITCH,
}


# ═══════════════════════════════════════════════════════
# MAIN INPUT LAYER
# ═══════════════════════════════════════════════════════

class PDFInputLayer:
    """Main input layer for processing PDF drawings and extracting fire alarm devices."""

    def __init__(self, scale_factor: float = 1.0):
        self.scale_factor = scale_factor

    def process(self, pdf_path: str) -> InputLayerResult:
        from parsers._path_security import (
            UnsafePathError,
            validate_file_size,
            validate_input_path,
        )
        _ALLOWED_EXTENSIONS = frozenset({".pdf"})
        _MAX_FILE_SIZE_BYTES = int(os.getenv("FIREAI_PDF_MAX_FILE_SIZE_BYTES", 200 * 1024 * 1024))
        try:
            safe_path = validate_input_path(
                pdf_path,
                allowed_extensions=_ALLOWED_EXTENSIONS,
                parser_name="PDFInputLayer",
            )
            validate_file_size(
                safe_path,
                max_size_bytes=_MAX_FILE_SIZE_BYTES,
                parser_name="PDFInputLayer",
            )
        except UnsafePathError as e:
            raise ValueError(str(e)) from e

        result = InputLayerResult(
            source_pdf=pdf_path,
            confidence_result=None
        )

        try:
            confidence = ParserConfidence(str(safe_path)).evaluate()
            result.confidence_result = confidence

            if confidence.gate == GateDecision.REJECT:
                result.errors.append("Drawing REJECTED by confidence gate")
                logger.warning("REJECTED: %s", confidence.message)
                return result

            if confidence.gate == GateDecision.CAUTION:
                result.warnings.append("Drawing marked CAUTION - manual review recommended")

        except Exception as e:
            result.errors.append(f"Confidence check failed: {e}")
            return result

        try:
            self._extract_data(str(safe_path), result)
        except Exception as e:
            import traceback
            full_tb = traceback.format_exc()
            result.errors.append(f"Data extraction failed: {e}")
            result.errors.append(f"Traceback: {full_tb}")
            logger.exception("Extraction error: %s\n%s", e, full_tb)

        return result

    def _extract_data(self, pdf_path: str, result: InputLayerResult):
        import _fitz_compat as fitz

        doc = fitz.open(pdf_path)

        for page_num, page in enumerate(doc, 1):
            if page_num == 1:
                result.metadata = self._extract_metadata(page)

            devices = self._extract_devices(page, page_num)
            result.devices.extend(devices)

            rooms = self._extract_rooms(page, page_num)
            result.rooms.extend(rooms)

        doc.close()

    def _extract_metadata(self, page) -> DrawingMetadata:
        text = page.get_text().lower()

        metadata = DrawingMetadata()

        match = re.search(r'(?:project|building)[:\s]*([^\n]+)', text)
        if match:
            metadata.building_name = match.group(1).strip()[:50]

        floor_match = re.search(r'(?:floor|level)[:\s]*(ground|first|second|third|1st|2nd|3rd|\d+)', text)
        if floor_match:
            metadata.floor_level = floor_match.group(1).strip()

        scale_match = re.search(r'scale[:\s]*(\d+[:/]\d+|1/8"|1/4"|3/32")', text)
        if scale_match:
            metadata.drawing_scale = scale_match.group(1).strip()

        date_match = re.search(r'(?:date|drawn)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
        if date_match:
            metadata.date = date_match.group(1).strip()

        designer_match = re.search(r'(?:designer|drawn by|prepared by)[:\s]*([^\n]+)', text)
        if designer_match:
            metadata.designer = designer_match.group(1).strip()[:50]

        rev_match = re.search(r'rev(?:ision)?[:\s]*([A-Z0-9]+)', text)
        if rev_match:
            metadata.revision = rev_match.group(1).strip()

        metadata.north_arrow = 'north' in text and 'arrow' in text

        return metadata

    def _extract_devices(self, page, page_num: int) -> list[ExtractedDevice]:
        devices = []
        text = page.get_text().lower()

        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        for symbol_pattern, device_type in NFPA_170_SYMBOLS.items():
            for match in re.finditer(re.escape(symbol_pattern), text):
                x, y = self._extract_coordinates_near(text, match.start(), page_width, page_height)
                room = self._extract_room_near(text, match.start())
                confidence = 0.7 if (x, y) != (0, 0) else 0.5

                devices.append(ExtractedDevice(
                    device_type=device_type,
                    x=x,
                    y=y,
                    page=page_num,
                    room=room,
                    confidence=confidence
                ))

        return self._deduplicate_devices(devices)

    def _extract_coordinates_near(self, text: str, position: int,
                              _page_width: float, _page_height: float) -> tuple[float, float]:
        window = text[max(0, position - 30):position + 30]

        coord_match = re.search(r'(\d+(?:\.\d+)?)[,\s]+(\d+(?:\.\d+)?)', window)
        if coord_match:
            try:
                x_raw = coord_match.group(1)
                y_raw = coord_match.group(2)
                if not x_raw.replace('.', '').isdigit() or not y_raw.replace('.', '').isdigit():
                    return (0.0, 0.0)
                x = float(x_raw)
                y = float(y_raw)
                return (x * float(self.scale_factor), y * float(self.scale_factor))
            except (ValueError, TypeError):
                pass

        return (0.0, 0.0)

    def _extract_room_near(self, text: str, position: int) -> str | None:
        window = text[max(0, position - 50):position + 50]

        room_patterns = [
            r'(?:room|r\.?|#)\s*(\d+[A-Za-z]?)',
            r'(?:rm|r)[\s.-]*(\d+)',
            r'\b(\d+[A-Za-z]?)\s*$',
        ]

        for pattern in room_patterns:
            match = re.search(pattern, window, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def _extract_rooms(self, page, _page_num: int) -> list[RoomBoundary]:  # NOSONAR:S3776: PDF room extraction must handle many layout patterns
        rooms = []
        text = page.get_text()
        text_lower = text.lower()

        KNOWN_ROOM_NAMES = [
            'corridor', 'lobby', 'office', 'kitchen', 'meeting',
            'bathroom', 'bedroom', 'warehouse', 'storage', 'server',
            'atrium'
        ]

        room_matches = re.finditer(
            r'room\s*([A-Z]?\d+[A-Za-z]?)',  # nosec: S5869 — no duplicate in character class
            text_lower,
            re.IGNORECASE
        )

        for match in room_matches:
            room_name = match.group(1).upper()
            area = self._extract_room_area(text_lower, match.start())
            ceiling = self._extract_ceiling_height(text_lower, match.start())

            try:
                bbox = page.get_text("bbox", match.span())
                if bbox and isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    try:
                        center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
                        center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
                    except (TypeError, ValueError):
                        center_x, center_y = 100.0, 100.0
                else:
                    center_x, center_y = 100.0, 100.0
            except Exception:
                center_x, center_y = 100.0, 100.0

            rooms.append(RoomBoundary(
                name=room_name,
                area_sqft=area or 100.0,
                center_x=center_x,
                center_y=center_y,
                ceiling_height=ceiling
            ))

        for room_keyword in KNOWN_ROOM_NAMES:
            pattern = re.compile(rf'\b{re.escape(room_keyword)}\b', re.IGNORECASE)
            for match in pattern.finditer(text_lower):
                room_name = match.group(0).title()
                if any(r.name.lower() == room_name.lower() for r in rooms):
                    continue

                area = self._extract_room_area(text_lower, match.start())
                ceiling = self._extract_ceiling_height(text_lower, match.start())

                try:
                    bbox = page.get_text("bbox", match.span())
                    if bbox and isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        try:
                            center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
                            center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
                        except (TypeError, ValueError):
                            center_x, center_y = 100.0, 100.0
                    else:
                        center_x, center_y = 100.0, 100.0
                except Exception:
                    center_x, center_y = 100.0, 100.0

                rooms.append(RoomBoundary(
                    name=room_name,
                    area_sqft=area or 25.0,
                    center_x=center_x,
                    center_y=center_y,
                    ceiling_height=ceiling
                ))

        return rooms

    def _extract_room_area(self, text: str, position: int) -> float | None:
        window = text[position:position + 200]

        area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft\.?|sf)', window)
        if area_match:
            try:
                return float(area_match.group(1))
            except ValueError:
                pass

        area_match2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:m2|m\.?²|sq\.?\s*m|square\s*m)', window)  # nosec: S8786 — no super-linear backtracking; all alternations are fixed-length
        if area_match2 is not None:
            try:
                area_val = float(area_match2.group(1))
                return area_val * 10.764
            except ValueError:
                pass

        return None

    def _extract_ceiling_height(self, text: str, position: int) -> float:
        window = text[max(0, position - 200):position + 200]

        height_patterns = [
            r'ceiling[:\s]*(\d+(?:\.\d+)?)\s*(?:ft|feet|\')',
            r'(\d+(?:\.\d+)?)\s*ft\s+ceiling',
            r'height[:\s]*(\d+(?:\.\d+)?)\s*(?:ft|feet|\')',
        ]

        for pattern in height_patterns:
            match = re.search(pattern, window, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        return 9.0

    def _deduplicate_devices(self, devices: list[ExtractedDevice]) -> list[ExtractedDevice]:
        seen = {}
        unique = []

        for d in devices:
            key = (d.device_type.value, d.room, d.page)
            if key not in seen:
                seen[key] = d
                unique.append(d)

        return unique


# ═══════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════

def process_drawing(pdf_path: str) -> InputLayerResult:
    layer = PDFInputLayer()
    return layer.process(pdf_path)


def quick_accept_check(pdf_path: str) -> tuple[bool, str]:
    try:
        confidence = ParserConfidence(pdf_path).evaluate()
        return (
            confidence.gate != GateDecision.REJECT,
            confidence.message
        )
    except Exception as e:
        return False, f"Error: {e}"
