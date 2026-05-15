"""
INPUT PIPELINE — Complete PDF to Coverage Report Pipeline
=================================================
يربط كل الطبقات: PDF → ParserConfidence → Extractors → CoverageEngine → Report

Author: The Consultant Who Refused to Lie
"""

import fitz
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GateDecision(Enum):
    """قرار البوابة."""
    REJECT = "REJECT"      # لا يدخل المحرك
    CAUTION = "CAUTION"    # يدخل لكن يحتاج مراجعة
    HIGH = "HIGH"         # يدخل بثقة عالية


class ReportStatus(Enum):
    """حالة التقرير."""
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"    # بعض المكونات مفقودة
    FAILED = "FAILED"     # فشل كامل


@dataclass
class PipelineResult:
    """نتيجة الـ Pipeline كاملة."""
    
    # Decision from ParserConfidence
    gate_decision: GateDecision
    gate_score: float
    
    # Extracted data
    walls: List = field(default_factory=list)
    rooms: List = field(default_factory=list)
    symbols: List = field(default_factory=list)
    dimensions: List = field(default_factory=list)
    
    # Coverage results  
    violations: List = field(default_factory=list)
    coverage_percentage: float = 0.0
    
    # Report metadata
    status: ReportStatus = ReportStatus.FAILED
    pdf_path: str = ""
    page_count: int = 0
    extraction_time_ms: float = 0.0
    warnings: List = field(default_factory=list)
    pe_review_required: bool = False
    
    def to_dict(self) -> dict:
        return {
            "gate": {
                "decision": self.gate_decision.value,
                "score": round(self.gate_score, 3)
            },
            "extracted": {
                "walls": len(self.walls),
                "rooms": len(self.rooms),
                "symbols": len(self.symbols),
                "dimensions": len(self.dimensions)
            },
            "coverage": {
                "percentage": round(self.coverage_percentage, 2),
                "violations": len(self.violations)
            },
            "status": self.status.value,
            "pe_review_required": self.pe_review_required,
            "warnings": self.warnings
        }


class InputPipeline:
    """
    Pipeline كامل: من PDF إلى تقرير تغطية.
    
    المسار:
    PDF → ParserConfidence Gate → GeometryExtractor → SymbolExtractor 
         → DimensionExtractor → CoverageEngine → Report
    """
    
    def __init__(self, standard=None):
        """
        تهيئة الـ Pipeline.
        
        Args:
            standard: NFPA standard (إذا لم يُعطَ، يُستخدم default)
        """
        self.standard = standard
        self._load_dependencies()
    
    def _load_dependencies(self):
        """تحميل_all dependencies."""
        # Import here to avoid circular imports
        global ParserConfidence, GeometryExtractor, DimensionExtractor
        global SymbolExtractor, CoverageService, Room, Device
        
        try:
            from parsers.parser_confidence import ParserConfidence, GateDecision
            from parsers.geometry_extractor import GeometryExtractor, WallElement
            from src.core.symbol_extractor import SymbolExtractor, SymbolType
            from src.core.dimension_extractor import DimensionExtractor
            from src.application.coverage_service import CoverageService
            from src.core.models import Room, Device
            
            self.ParserConfidence = ParserConfidence
            self.GeometryExtractor = GeometryExtractor
            self.SymbolExtractor = SymbolExtractor
            self.DimensionExtractor = DimensionExtractor
            self.CoverageService = CoverageService
            self.Room = Room
            self.Device = Device
            
            print("✅ All dependencies loaded")
        except ImportError as e:
            print(f"⚠️ Missing dependency: {e}")
            raise
    
    def process(self, pdf_path: str, page: int = 0) -> PipelineResult:
        """
        معالجة PDF كامل وإنتاج تقرير تغطية.
        
        Args:
            pdf_path: مسار ملف PDF
            page: رقم الصفحة (default: 0)
            
        Returns:
            PipelineResult with full report
        """
        import time
        start_time = time.time()
        
        result = PipelineResult(
            pdf_path=pdf_path,
            gate_decision=GateDecision.REJECT,
            gate_score=0.0,
            status=ReportStatus.FAILED
        )
        
        # التحقق من الملف
        if not os.path.exists(pdf_path):
            result.warnings.append(f"File not found: {pdf_path}")
            return result
        
        # 1. ParserConfidence Gate
        print("🔍 [1/5] Running ParserConfidence Gate...")
        gate_result = self._run_gate(pdf_path, page)
        result.gate_decision = gate_result["decision"]
        result.gate_score = gate_result["score"]
        result.warnings.extend(gate_result.get("warnings", []))
        
        if result.gate_decision == GateDecision.REJECT:
            result.status = ReportStatus.FAILED
            result.warnings.append("REJECTED by ParserConfidence Gate")
            result.extraction_time_ms = (time.time() - start_time) * 1000
            return result
        
        # 2. Extract Walls
        print("🧱 [2/5] Extracting walls...")
        walls_result = self._extract_walls(pdf_path, page)
        result.walls = walls_result["walls"]
        result.rooms = walls_result["rooms"]
        
        if not result.walls:
            result.pe_review_required = True
            result.warnings.append("No walls extracted - PE REVIEW REQUIRED")
        
        # 3. Extract Symbols
        print("🏷️ [3/5] Extracting symbols...")
        symbols_result = self._extract_symbols(pdf_path, page)
        result.symbols = symbols_result["symbols"]
        
        # 4. Extract Dimensions
        print("📏 [4/5] Extracting dimensions...")
        dims_result = self._extract_dimensions(pdf_path, page)
        result.dimensions = dims_result["dimensions"]
        
        # 5. Run Coverage Engine
        print("🛡️ [5/5] Running coverage engine...")
        coverage_result = self._run_coverage(result)
        result.violations = coverage_result["violations"]
        result.coverage_percentage = coverage_result["percentage"]
        
        # Determine status
        result.status = self._determine_status(result)
        
        # PE Review required?
        result.pe_review_required = (
            result.gate_decision == GateDecision.CAUTION or
            not result.walls or
            result.coverage_percentage < 50.0 or
            len(result.violations) > 0
        )
        
        result.extraction_time_ms = (time.time() - start_time) * 1000
        result.page_count = self._get_page_count(pdf_path)
        
        return result
    
    def _run_gate(self, pdf_path: str, page: int) -> dict:
        """تشغيل ParserConfidence Gate."""
        try:
            parser = self.ParserConfidence(pdf_path)
            result = parser.evaluate()
            score = result.score
            decision = result.gate
            
            return {
                "score": score,
                "decision": decision,
                "warnings": result.details.get("warnings", [])
            }
        except Exception as e:
            return {
                "score": 0.0,
                "decision": GateDecision.REJECT,
                "warnings": [f"Gate error: {str(e)}"]
            }
    
    def _map_decision(self, decision_str: str) -> GateDecision:
        """Map decision string to enum."""
        mapping = {
            "REJECT": GateDecision.REJECT,
            "CAUTION": GateDecision.CAUTION,
            "HIGH": GateDecision.HIGH,
            "HIGH_CONFIDENCE": GateDecision.HIGH
        }
        return mapping.get(decision_str.upper(), GateDecision.REJECT)
    
    def _extract_walls(self, pdf_path: str, page: int) -> dict:
        """استخراج الجدران."""
        try:
            extractor = self.GeometryExtractor(pdf_path, page)
            walls = extractor.extract_walls()
            rooms = extractor.extract_rooms(walls) if hasattr(extractor, 'extract_rooms') else []
            
            return {"walls": walls, "rooms": rooms}
        except Exception as e:
            return {"walls": [], "rooms": [], "error": str(e)}
    
    def _extract_symbols(self, pdf_path: str, page: int) -> dict:
        """استخراج الرموز."""
        try:
            extractor = self.SymbolExtractor(pdf_path, page)
            symbols = extractor.extract_symbols()
            
            return {"symbols": symbols}
        except Exception as e:
            return {"symbols": [], "error": str(e)}
    
    def _extract_dimensions(self, pdf_path: str, page: int) -> dict:
        """استخراج الأبعاد."""
        try:
            extractor = self.DimensionExtractor(pdf_path, page)
            dimensions = extractor.extract_dimensions()
            
            return {"dimensions": dimensions}
        except Exception as e:
            return {"dimensions": [], "error": str(e)}
    
    def _run_coverage(self, result: PipelineResult) -> dict:
        """تشغيل Coverage Engine."""
        if not result.rooms:
            return {"violations": [], "percentage": 0.0}
        
        try:
            # Convert walls to Room and Devices
            room = self._build_room_from_walls(result)
            if not room:
                return {"violations": [], "percentage": 0.0}
            
            # Convert symbols to devices
            devices = self._build_devices_from_symbols(result.symbols)
            
            # Run coverage
            coverage = self.CoverageService()
            violations = coverage.check_coverage(room, devices, self.standard)
            
            # Calculate percentage
            percentage = self._calculate_coverage_percentage(
                room, devices, violations
            )
            
            return {"violations": violations, "percentage": percentage}
        except Exception as e:
            return {"violations": [], "percentage": 0.0, "error": str(e)}
    
    def _build_room_from_walls(self, result: PipelineResult) -> Optional[object]:
        """بناء Room من الجدران المستخلصة."""
        if not result.rooms:
            return None
        
        # Use largest room
        largest_room = max(result.rooms, key=lambda r: getattr(r, 'area', 0))
        return largest_room
    
    def _build_devices_from_symbols(self, symbols: List) -> List:
        """تحويل الرموز إلى أجهزة."""
        devices = []
        for sym in symbols:
            if hasattr(sym, 'bbox'):
                # Symbol has location
                device = self.Device(
                    device_type=getattr(sym, 'symbol_type', 'UNKNOWN'),
                    x=sym.bbox[0],
                    y=sym.bbox[1],
                    # Map symbol type to device type
                )
                devices.append(device)
        return devices
    
    def _calculate_coverage_percentage(self, room, devices: List, violations: List) -> float:
        """حساب نسبة التغطية."""
        if not room:
            return 0.0
        
        room_area = getattr(room, 'area', 0)
        if room_area <= 0:
            return 0.0
        
        # NFPA spacing: ~9m for smoke detectors
        # Each device covers ~63 sqm (9m radius)
        device_coverage = 63.0  # ~9m radius circle
        covered = len(devices) * device_coverage
        
        percentage = min(100.0, (covered / room_area) * 100)
        return percentage
    
    def _determine_status(self, PipelineResult) -> ReportStatus:
        """تحديد حالة التقرير."""
        if not PipelineResult.walls:
            return ReportStatus.PARTIAL
        if PipelineResult.coverage_percentage >= 80:
            return ReportStatus.COMPLETE
        return ReportStatus.PARTIAL
    
    def _get_page_count(self, pdf_path: str) -> int:
        """عدد صفحات PDF."""
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except:
            return 0


def run_pipeline(pdf_path: str, page: int = 0) -> PipelineResult:
    """
    دالة سريعة لتشغيل الـ Pipeline.
    
    Args:
        pdf_path: مسار ملف PDF
        page: رقم الصفحة
        
    Returns:
        PipelineResult full report
    """
    pipeline = InputPipeline()
    return pipeline.process(pdf_path, page)


# For testing
if __name__ == "__main__":
    import tempfile
    import fitz
    
    # Create test PDF
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Add walls
    page.draw_rect(fitz.Rect(50, 50, 300, 300), color=(0,0,0), width=2, fill=(0.9,0.9,0.9))
    # Add text
    page.insert_text((100, 100), "SMOKE DETECTOR SD-101", fontsize=10)
    page.insert_text((100, 120), "Ceiling Height: 3.5 m", fontsize=10)
    doc.save("/tmp/test_pipeline.pdf")
    doc.close()
    
    # Run pipeline
    result = run_pipeline("/tmp/test_pipeline.pdf")
    print(f"""
=== Pipeline Result ===
Gate: {result.gate_decision.value} ({result.gate_score:.2f})
Walls: {len(result.walls)}
Rooms: {len(result.rooms)}  
Symbols: {len(result.symbols)}
Dimensions: {len(result.dimensions)}
Coverage: {result.coverage_percentage:.1f}%
Violations: {len(result.violations)}
Status: {result.status.value}
PE Review Required: {result.pe_review_required}
""")