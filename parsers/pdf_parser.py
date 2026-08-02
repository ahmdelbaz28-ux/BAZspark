# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
pdf_parser.py — FireAI PDF Floor Plan Parser
Extracts fire alarm device locations from PDF drawings.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from parsers._base import ParserBase
from parsers._device_types import DeviceType
from parsers._path_security import UnsafePathError

logger = logging.getLogger("fireai.pdf_parser")


# ═══════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════

@dataclass
class PDFDevice:
    """Single fire device from PDF."""

    device_type: str
    location: str
    page: int
    x: float
    y: float

    def to_dict(self) -> dict:
        return {
            "type": self.device_type,
            "location": self.location,
            "page": self.page,
            "coordinates": (self.x, self.y)
        }


@dataclass
class PDFParseResult:
    """Result of parsing PDF floor plan."""

    source_file: str
    success: bool
    page_count: int = 0
    devices: List[PDFDevice] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    text_content: str = ""

    @property
    def device_count(self) -> int:
        return len(self.devices)


# ═══════════════════════════════════════════════════════
# DEVICE PATTERNS (NFPA 72 compliant)
# ═══════════════════════════════════════════════════════

DEVICE_PATTERNS = [
    (r'smoke\s*detector', DeviceType.SMOKE_DETECTOR),
    (r'heat\s*detector', DeviceType.HEAT_DETECTOR),
    (r'photoelectric\s*detector', DeviceType.SMOKE_DETECTOR),
    (r'ionization\s*detector', DeviceType.SMOKE_DETECTOR),
    (r'fixed\s*temp', DeviceType.HEAT_DETECTOR),
    (r'rate-of-rise', DeviceType.HEAT_DETECTOR),
    (r'pull\s*station', DeviceType.MANUAL_PULL_STATION),
    (r'fire\s*alarm\s*pull', DeviceType.MANUAL_PULL_STATION),
    (r'manual\s*pull', DeviceType.MANUAL_PULL_STATION),
    (r'break\s*glass', DeviceType.MANUAL_PULL_STATION),
    (r'horn[\s-]*strobe', DeviceType.HORN_STROBE),
    (r'horn', DeviceType.HORN),
    (r'strobe', DeviceType.STROBE),
    (r'bell', DeviceType.BELL),
    (r'speaker', DeviceType.SPEAKER),
    (r'notification', 'NOTIFICATION'),
    (r'fire\s*alarm\s*panel', 'FAP'),
    (r'control\s*panel', 'FAP'),
    (r'facp', 'FAP'),
    (r'main\s*panel', 'FAP'),
    (r'sprinkler', DeviceType.SPRINKLER),
    (r'flow\s*switch', DeviceType.FLOW_SWITCH),
    (r'tamper\s*switch', DeviceType.TAMPER_SWITCH),
    (r'power\s*supply', 'POWER_SUPPLY'),
    (r'battery', 'BATTERY'),
]


@dataclass
class PDFParser(ParserBase):
    """
    Parses PDF floor plans for fire alarm devices.
    """

    allowed_extensions: frozenset[str] = frozenset({'.pdf'})

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence
        self._device_cache: Dict[str, str] = {}
        self.max_file_size_bytes: int = int(
            os.getenv("FIREAI_PDF_MAX_FILE_SIZE_BYTES", 200 * 1024 * 1024)
        )

    def parse(self, pdf_path: str) -> PDFParseResult:

        try:
            safe_path = self.validate_input(pdf_path)
        except UnsafePathError as e:
            return PDFParseResult(source_file=pdf_path, success=False, errors=[f"SECURITY: {e}"])
        except FileNotFoundError as e:
            return PDFParseResult(source_file=pdf_path, success=False, errors=[str(e)])

        result = PDFParseResult(source_file=pdf_path, success=False)

        try:
            devices, text, page_count = self._parse_pdfplumber(str(safe_path))
            result.devices = devices
            result.text_content = text
            result.page_count = page_count
            result.success = len(devices) > 0
            if len(text) > 0 and len(devices) == 0:
                result.warnings.append("Text extracted but no fire devices identified")
        except ImportError as e:
            result.errors.append(f"Missing dependency: {e}")
        except Exception as e:
            result.errors.append(f"Parse error: {type(e).__name__}: {e}")

        return result

    def _parse_pdfplumber(self, pdf_path: str):
        import pdfplumber

        devices = []
        all_text = []

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()

                if not text or len(text.strip()) < 50:
                    logger.info("Page %s: No text found, trying OCR...", page_num)
                    text = self._ocr_page(page)
                    if text:
                        logger.info("Page %s: OCR recovered %s chars", page_num, len(text))

                if text:
                    all_text.append(text)
                    page_devices = self._find_devices(text, page_num)
                    devices.extend(page_devices)

                tables = page.extract_tables()
                for table in tables:
                    if table:
                        table_text = ' '.join(str(cell) for row in table for cell in row)
                        table_devices = self._find_devices(table_text, page_num)
                        devices.extend(table_devices)

        devices = self._deduplicate_devices(devices)
        return devices, '\n'.join(all_text), page_count

    def _ocr_page(self, page) -> str:
        try:
            from fireai.integration.document_intelligence import is_doctr_available, ocr_image
            if is_doctr_available():
                img = page.to_image(resolution=200)
                import io
                buf = io.BytesIO()
                img.original.save(buf, format="PNG")
                image_bytes = buf.getvalue()

                ocr_result = ocr_image(image_bytes)
                if ocr_result and len(ocr_result) > 0:
                    text = ocr_result[0].full_text
                    if text and len(text.strip()) > 10:
                        logger.info("DocTR OCR: extracted %d chars", len(text))
                        return text
        except Exception as e:
            logger.debug("DocTR OCR unavailable, falling back to Tesseract: %s", e)

        try:
            import pytesseract
            os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr'
            img = page.to_image(resolution=150)
            pil_img = img.original
            return pytesseract.image_to_string(
                pil_img,
                lang='eng',
                config='--tessdata-dir /usr/share/tesseract-ocr/5/tessdata'
            )
        except ImportError:
            logger.warning("pytesseract not installed")
            return ""
        except Exception as e:
            logger.exception("OCR failed: %s", e)
            return ""

    def _find_devices(self, text: str, page: int) -> List[PDFDevice]:
        devices = []
        text_lower = text.lower()

        for pattern, device_type in DEVICE_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)

            for match in matches:
                location = self._extract_location(text, match.start())
                x, y = self._guess_coordinates(text, match.start())

                devices.append(PDFDevice(
                    device_type=str(device_type.value) if hasattr(device_type, 'value') else str(device_type),
                    location=location or "Unknown",
                    page=page,
                    x=x,
                    y=y
                ))

        return devices

    def _extract_location(self, text: str, position: int) -> Optional[str]:
        window = text[max(0, position - 50):position + 50]

        room_patterns = [
            r'(?:room|r[\s-]*|#)\s*(\d+[A-Za-z]?)',
            r'((?:\d+)[A-Za-z]?)\s*$',
            r'([A-Z]\d+)',
        ]

        for pattern in room_patterns:
            match = re.search(pattern, window, re.IGNORECASE)
            if match:
                return f"Room {match.group(1)}"

        return None

    def _guess_coordinates(self, _text: str, _position: int) -> tuple:
        return (0.0, 0.0)

    def _extract_layout_devices(self, _page_num: int) -> List[PDFDevice]:
        devices = []
        # TODO: Implement symbol detection for PDF layout devices (placeholder)
        return devices

    def _deduplicate_devices(self, devices: List[PDFDevice]) -> List[PDFDevice]:
        seen = set()
        unique = []

        for d in devices:
            key = (d.device_type, d.location, d.page)
            if key not in seen:
                seen.add(key)
                unique.append(d)

        return unique


# ═══════════════════════════════════════════════════════
# REPORT GENERATOR
# ═══════════════════════════════════════════════════════

class PDFReportGenerator:
    """Generate PDF inspection reports."""

    def __init__(self):
        self.parser = PDFParser()

    def generate_report(self, pdf_path: str) -> dict:
        result = self.parser.parse(pdf_path)

        device_counts: Dict[str, int] = {}
        for d in result.devices:
            device_counts[d.device_type] = device_counts.get(d.device_type, 0) + 1

        return {
            "source": result.source_file,
            "success": result.success,
            "page_count": result.page_count,
            "device_count": result.device_count,
            "device_counts": device_counts,
            "devices": [d.to_dict() for d in result.devices],
            "errors": result.errors,
            "warnings": result.warnings,
            "smoke_detectors": device_counts.get("SMOKE_DETECTOR", 0),
            "heat_detectors": device_counts.get("HEAT_DETECTOR", 0),
            "pull_stations": device_counts.get("MANUAL_PULL_STATION", 0),
            "notification_appliances": (
                device_counts.get("HORN", 0) +
                device_counts.get("STROBE", 0) +
                device_counts.get("HORN_STROBE", 0)
            ),
        }

    def print_report(self, pdf_path: str) -> str:
        report = self.generate_report(pdf_path)

        lines = [
            "=" * 60,
            "FIRE ALARM PDF INSPECTION REPORT",
            "=" * 60,
            f"Source: {report['source']}",
            f"Status: {'SUCCESS' if report['success'] else 'FAILED'}",
            f"Pages: {report['page_count']}",
            "",
            "-" * 40,
            "DEVICE SUMMARY",
            "-" * 40,
        ]

        for dtype, count in report['device_counts'].items():
            lines.append(f"  {dtype}: {count}")

        lines.extend([
            "",
            "-" * 40,
            "NFPA 72 COMPLIANCE",
            "-" * 40,
            f"  Smoke Detectors: {report['smoke_detectors']}",
            f"  Heat Detectors: {report['heat_detectors']}",
            f"  Pull Stations: {report['pull_stations']}",
            f"  Notification: {report['notification_appliances']}",
        ])

        if report['errors']:
            lines.extend(["", "ERRORS:"] + report['errors'])

        if report['warnings']:
            lines.extend(["", "WARNINGS:"] + report['warnings'])

        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════

def parse_pdf(pdf_path: str) -> PDFParseResult:
    """Quick parse PDF floor plan."""
    parser = PDFParser()
    return parser.parse(pdf_path)


def generate_inspection_report(pdf_path: str) -> dict:
    """Generate inspection report."""
    generator = PDFReportGenerator()
    return generator.generate_report(pdf_path)
