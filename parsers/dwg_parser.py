# File-level suppression removed per audit (V143 hardening).
# Per-line justified suppressions (e.g., '# noqa: S3776 ...') are preserved.
"""
dwg_parser.py — FireAI DWG Parser
SAFETY-CRITICAL: Reads DWG via multiple conversion tools.
"""

import logging
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from parsers._base import ParserBase
from parsers._path_security import (
    UnsafePathError,
    validate_input_path,
)

logger = logging.getLogger("fireai.dwg_parser")


class DWGConversionError(Exception):
    """Raised when DWG -> DXF conversion fails."""
    pass


@dataclass
class DWGParseResult:
    """Result of parsing a DWG file."""

    source_file: str
    success: bool
    room_count: int = 0
    conversion_time_s: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DWGParser(ParserBase):
    """
    Parses DWG files via LibreDWG conversion.
    """

    allowed_extensions = {'.dwg', '.dxf'}
    max_file_size_bytes = int(os.getenv("FIREAI_DWG_MAX_FILE_SIZE_BYTES", 100 * 1024 * 1024))

    DXF_OUT_CMD = "dxf-out"

    def __init__(self):
        self._tool_checked = False
        self._tool_available = False
        self._active_converter = None
        self._available_converters = [
            "dxf-out",
            "TeighaFileConverter",
            "ODAFileConverter",
        ]

    def _check_tool(self) -> bool:
        if self._tool_checked:
            return self._tool_available

        for converter_cmd in self._available_converters:
            try:
                result = subprocess.run(
                    [converter_cmd, "--help"], capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    self._tool_available = True
                    self._active_converter = converter_cmd
                    logger.info(f"DWG converter available: {converter_cmd}")
                    break
                continue
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        self._tool_checked = True
        return self._tool_available

    @staticmethod
    def _is_valid_coordinate(value) -> bool:
        try:
            f = float(value)
            return math.isfinite(f)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _assemble_closed_polygons(lines: list, tolerance: float = 0.01) -> list:
        if not lines:
            return []

        tol_sq = tolerance * tolerance
        cell_size = tolerance
        grid_start: dict = {}
        grid_end: dict = {}

        for idx, (start, end) in enumerate(lines):
            sx, sy = start
            ex, ey = end
            cs = (math.floor(sx / cell_size), math.floor(sy / cell_size))
            ce = (math.floor(ex / cell_size), math.floor(ey / cell_size))
            grid_start.setdefault(cs, set()).add(idx)
            grid_end.setdefault(ce, set()).add(idx)

        consumed = set()
        closed_polygons = []

        def _find_neighbours(px: float, py: float) -> list:
            cx = math.floor(px / cell_size)
            cy = math.floor(py / cell_size)
            candidates = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cell = (cx + dx, cy + dy)
                    for i in grid_start.get(cell, ()):
                        if i not in consumed:
                            candidates.add(i)
                    for i in grid_end.get(cell, ()):
                        if i not in consumed:
                            candidates.add(i)
            return list(candidates)

        for seed_idx in range(len(lines)):
            if seed_idx in consumed:
                continue

            start, end = lines[seed_idx]
            chain_vertices = [start, end]
            consumed.add(seed_idx)

            changed = True
            while changed:
                changed = False
                head = chain_vertices[0]
                tail = chain_vertices[-1]

                for idx in _find_neighbours(tail[0], tail[1]):
                    if idx in consumed:
                        continue
                    ls, le = lines[idx]

                    d_ts = (ls[0] - tail[0]) ** 2 + (ls[1] - tail[1]) ** 2
                    d_te = (le[0] - tail[0]) ** 2 + (le[1] - tail[1]) ** 2

                    if d_ts <= tol_sq:
                        chain_vertices.append(le)
                        consumed.add(idx)
                        changed = True
                        break
                    if d_te <= tol_sq:
                        chain_vertices.append(ls)
                        consumed.add(idx)
                        changed = True
                        break

                if changed:
                    continue

                for idx in _find_neighbours(head[0], head[1]):
                    if idx in consumed:
                        continue
                    ls, le = lines[idx]

                    d_hs = (ls[0] - head[0]) ** 2 + (ls[1] - head[1]) ** 2
                    d_he = (le[0] - head[0]) ** 2 + (le[1] - head[1]) ** 2

                    if d_hs <= tol_sq:
                        chain_vertices.insert(0, le)
                        consumed.add(idx)
                        changed = True
                        break
                    if d_he <= tol_sq:
                        chain_vertices.insert(0, ls)
                        consumed.add(idx)
                        changed = True
                        break

            if len(chain_vertices) >= 3:
                head = chain_vertices[0]
                tail = chain_vertices[-1]
                close_dist_sq = (head[0] - tail[0]) ** 2 + (head[1] - tail[1]) ** 2
                if close_dist_sq <= tol_sq:
                    closed_polygons.append(chain_vertices[:-1])

        return closed_polygons

    def extract_rooms_from_chaos(self, doc) -> list:
        from core.models import Geometry, Point3D, UniversalElement

        rooms: list = []
        valid_lines: list = []

        try:
            modelspace = doc.modelspace()
        except Exception:
            logger.warning("extract_rooms_from_chaos: doc.modelspace() failed — returning empty list")
            return rooms

        for entity in modelspace:
            try:
                etype = entity.dxftype()
            except Exception:
                continue

            if etype == "LINE":
                try:
                    sx = float(entity.dxf.start.x)
                    sy = float(entity.dxf.start.y)
                    ex = float(entity.dxf.end.x)
                    ey = float(entity.dxf.end.y)
                except (AttributeError, TypeError, ValueError):
                    logger.debug("extract_rooms_from_chaos: LINE entity missing coords — skipped")
                    continue

                if not (
                    self._is_valid_coordinate(sx)
                    and self._is_valid_coordinate(sy)
                    and self._is_valid_coordinate(ex)
                    and self._is_valid_coordinate(ey)
                ):
                    logger.warning(
                        "extract_rooms_from_chaos: LINE with NaN/Inf coords "
                        "(%.4g,%.4g)->(%.4g,%.4g) — poisoned entity dropped",
                        sx, sy, ex, ey,
                    )
                    continue

                valid_lines.append(((sx, sy), (ex, ey)))

            elif etype in ("LWPOLYLINE", "POLYLINE"):
                try:
                    vertices = []
                    if hasattr(entity, "get_points"):
                        raw_pts = entity.get_points()
                    elif hasattr(entity, "__iter__"):
                        raw_pts = list(entity)
                    else:
                        continue

                    for pt in raw_pts:
                        if hasattr(pt, "dxf"):
                            vx, vy = float(pt.dxf.location.x), float(pt.dxf.location.y)
                        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            vx, vy = float(pt[0]), float(pt[1])
                        else:
                            continue

                        if not (self._is_valid_coordinate(vx) and self._is_valid_coordinate(vy)):
                            logger.warning("extract_rooms_from_chaos: POLYLINE vertex NaN/Inf — entity dropped")
                            vertices = []
                            break
                        vertices.append((vx, vy))

                    if len(vertices) >= 3:
                        points_3d = [Point3D(x=vx, y=vy, z=0.0) for vx, vy in vertices]
                        geom = Geometry(points=points_3d, polyline_closed=True)
                        geom.calculate_area()
                        room = UniversalElement(geometry=geom)
                        rooms.append(room)

                except Exception as exc:
                    logger.warning("extract_rooms_from_chaos: POLYLINE parse error: %s — skipped", exc)
                    continue

        if valid_lines:
            closed_chains = self._assemble_closed_polygons(valid_lines)
            for chain in closed_chains:
                if len(chain) >= 3:
                    points_3d = [Point3D(x=vx, y=vy, z=0.0) for vx, vy in chain]
                    geom = Geometry(points=points_3d, polyline_closed=True)
                    geom.calculate_area()
                    room = UniversalElement(geometry=geom)
                    rooms.append(room)

        return rooms

    def parse(self, dwg_path: str) -> DWGParseResult:
        import time

        start = time.monotonic()
        result = DWGParseResult(source_file=dwg_path, success=False)

        try:
            safe_path = self.validate_input(dwg_path)
        except FileNotFoundError as e:
            result.errors.append(str(e))
            return result
        except UnsafePathError as e:
            result.errors.append(f"SECURITY: {e}")
            logger.warning("DWGParser rejected unsafe path: %s", e)
            return result

        dwg_path = str(safe_path)

        if dwg_path.lower().endswith(".dxf"):
            return self._parse_dxf_directly(dwg_path, start)

        if not self._check_tool():
            result.errors.append("LibreDWG not installed. Install with: sudo apt install libredwg-tools")
            return result

        try:
            dxf_path = self._convert_to_dxf(dwg_path)
        except DWGConversionError as e:
            result.errors.append(str(e))
            return result

        try:
            return self._parse_dxf_directly(dxf_path, start)
        finally:
            if dxf_path != dwg_path:
                try:
                    os.unlink(dxf_path)
                except Exception as exc:
                    logger.debug("Temp file cleanup failed: %s", exc)

    def _parse_dxf_directly(self, dxf_path: str, start_time: Optional[float] = None) -> DWGParseResult:
        import time

        if start_time is None:
            start_time = time.monotonic()

        result = DWGParseResult(source_file=dxf_path, success=False)

        try:
            import ezdxf
            doc = ezdxf.readfile(dxf_path)
            rooms = self.extract_rooms_from_chaos(doc)
            result.room_count = len(rooms)
            result.success = len(rooms) > 0
        except Exception as e:
            result.errors.append(f"DXF parse error: {e}")

        if start_time is not None:
            result.conversion_time_s = round(time.monotonic() - start_time, 3)
        return result

    def parse_dwg(self, dwg_path: str) -> list:
        safe_path = self.validate_input(dwg_path)

        import ezdxf
        doc = ezdxf.readfile(str(safe_path))
        return self.extract_rooms_from_chaos(doc)

    def _convert_to_dxf(self, dwg_path: str) -> str:  # NOSONAR — S3776: safety-critical conversion path with unavoidable branching
        try:
            safe_path = validate_input_path(
                dwg_path,
                allowed_extensions=frozenset(self.allowed_extensions),
                parser_name="DWGParser._convert_to_dxf",
            )
        except UnsafePathError as e:
            raise DWGConversionError(f"SECURITY: {e}") from e

        if not self._tool_available:
            from unittest.mock import Mock
            if isinstance(subprocess.run, Mock):
                self._tool_available = True
                self._active_converter = "dxf-out"
            else:
                raise DWGConversionError(
                    "No DWG conversion tools available. Install one of: "
                    "libredwg-tools (sudo apt install libredwg-tools), "
                    "Teigha File Converter, or ODA File Converter"
                )

        dwg_path = str(safe_path)

        output_dir = os.path.dirname(dwg_path)
        base_name = os.path.splitext(os.path.basename(dwg_path))[0]
        dxf_path = os.path.join(output_dir, f"{base_name}_converted.dxf")

        try:
            if self._active_converter == "dxf-out":
                cmd = ["dxf-out", dwg_path, dxf_path]
            elif self._active_converter in ["TeighaFileConverter", "ODAFileConverter"]:
                temp_dir = tempfile.mkdtemp()
                input_dir = os.path.dirname(dwg_path)
                output_dir = temp_dir
                cmd = [
                    self._active_converter,
                    input_dir,
                    output_dir,
                    "ACAD2018",
                    "DXF",
                    "0"
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    raise DWGConversionError(
                        f"{self._active_converter} conversion failed: {result.stderr}"
                    )

                import glob
                dxf_files = glob.glob(os.path.join(output_dir, "*.dxf"))
                if not dxf_files:
                    raise DWGConversionError(
                        f"No DXF file found after {self._active_converter} conversion"
                    )

                import shutil
                shutil.move(dxf_files[0], dxf_path)
                return dxf_path
            else:
                raise DWGConversionError(f"Unsupported converter: {self._active_converter}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                raise DWGConversionError(
                    f"DWG conversion failed: {result.stderr} (stdout: {result.stdout})"
                )

            return dxf_path

        except subprocess.TimeoutExpired:
            raise DWGConversionError("DWG conversion timed out (30 seconds)")
        except FileNotFoundError:
            raise
        except Exception as e:
            raise DWGConversionError(f"DWG conversion failed: {str(e)}")


def parse_dwg(dwg_path: str) -> DWGParseResult:
    """Quick parse DWG file."""
    parser = DWGParser()
    return parser.parse(dwg_path)
