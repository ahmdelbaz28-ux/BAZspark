"""
FireAI DWG Parser - AutoCAD DWG file parser
"""

import logging
from typing import List, Optional

from core.models import (
    UniversalElement, ElementType, Point3D, Geometry, 
    SemanticProperties, ChangeSource
)

logger = logging.getLogger(__name__)


class DWGParser:
    """
    محلل ملفات AutoCAD DWG
    """
    
    def __init__(self):
        logger.info("DWG Parser initialized")
    
    def parse_dwg(self, dwg_path: str) -> List[UniversalElement]:
        """
        تحليل ملف DWG واستخراج العناصر
        
        في البداية، نستخدم ezdxf library
        لاحقاً، سنستخدم AutoCAD COM API للتطبيق الحقيقي
        """
        try:
            import ezdxf
            
            doc = ezdxf.readfile(dwg_path)
            msp = doc.modelspace()
            
            elements = []
            
            for entity in msp:
                element = self._convert_entity_to_universal(entity, dwg_path)
                if element:
                    elements.append(element)
            
            logger.info(f"Parsed {len(elements)} elements from {dwg_path}")
            return elements
        
        except ImportError:
            logger.warning("ezdxf not installed. Install with: pip install ezdxf")
            return []
        except Exception as e:
            logger.error(f"Error parsing DWG {dwg_path}: {e}")
            return []
    
    def _convert_entity_to_universal(self, entity, source_file: str) -> Optional[UniversalElement]:
        """تحويل كائن DXF إلى Universal Element"""
        try:
            element_type = ElementType.UNKNOWN
            points = []
            
            # Determine type based on entity type
            if entity.dxftype() == 'LWPOLYLINE':
                points = [Point3D(x, y, 0) for x, y in entity.get_points()]
                
                # Heuristic: check layer name
                layer = entity.dxf.layer.upper()
                if 'WALL' in layer:
                    element_type = ElementType.WALL
                elif 'ROOM' in layer:
                    element_type = ElementType.ROOM
                elif 'DOOR' in layer:
                    element_type = ElementType.DOOR
                else:
                    element_type = ElementType.EQUIPMENT
            
            elif entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                points = [Point3D(start[0], start[1], start[2]), 
                         Point3D(end[0], end[1], end[2])]
                element_type = ElementType.EQUIPMENT
            
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                points = [Point3D(center[0], center[1], center[2])]
                element_type = ElementType.EQUIPMENT
            
            else:
                # Skip unsupported types
                return None
            
            if not points:
                return None
            
            # Create Universal Element
            geometry = Geometry(points=points, polyline_closed=True if entity.dxftype() == 'LWPOLYLINE' else False)
            geometry.calculate_area()
            geometry.calculate_perimeter()
            
            properties = SemanticProperties(
                element_type=element_type,
                name=entity.dxf.layer,
                layer=entity.dxf.layer
            )
            
            element = UniversalElement(
                properties=properties,
                geometry=geometry,
                source_file=source_file,
                last_modified_by=ChangeSource.AUTOCAD.value
            )
            
            # Store AutoCAD handle if available
            if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'handle'):
                element.autocad_handle = entity.dxf.handle
            
            return element
        
        except Exception as e:
            logger.error(f"Error converting entity: {e}")
            return None