"""
auto_placement.py - خوارزمية اقتراح مواقع الأجهزة (شبكة متداخلة)
الوصف: توزع الأجهزة بشكل متداخل (Staggered) على كامل طول وعرض الغرفة
       لضمان تغطية مثالية حتى في الغرف الضيقة.
"""
import math
from typing import List, Literal
from src.core.models import Room, Device, DeviceType, Point

def suggest_devices(
    room: Room,
    spacing: float,
    pattern: Literal["staggered", "rectilinear"] = "staggered"
) -> List[Device]:
    """
    يقترح شبكة أجهزة متداخلة (أو مستقيمة) بناءً على أبعاد الغرفة والتباعد المسموح.
    - spacing: أقصى مسافة بين جهازين متجاورين (مثلاً 9.1م لـ NFPA 72).
    """
    if not room.polygon or not room.polygon.exterior:
        return []

    # 1. أبعاد الصندوق المحيط
    coords = [(p.x, p.y) for p in room.polygon.exterior]
    min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
    min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)

    room_width = max_x - min_x
    room_height = max_y - min_y

    # 2. لا هامش - نغطي كل المساحة
    edge_margin = max(0.3, spacing / 6)  # Dynamic margin based on spacing to avoid wall edge cases

    # 3. المساحة الفعالة
    eff_w = max(0.0, room_width - 2 * edge_margin)
    eff_h = max(0.0, room_height - 2 * edge_margin)

    # 4. عدد الأعمدة والصفوف
    cols = max(1, math.ceil(eff_w / spacing) + 1) if eff_w > 0 else 1
    rows = max(1, math.ceil(eff_h / spacing) + 1) if eff_h > 0 else 1

    # 5. التباعد الفعلي
    x_step = eff_w / (cols - 1) if cols > 1 else 0.0
    y_step = eff_h / (rows - 1) if rows > 1 else 0.0

    devices = []
    for i in range(cols):
        for j in range(rows):
            x = min_x + edge_margin + i * x_step
            y = min_y + edge_margin + j * y_step

            # الشبكة المتداخلة: إزاحة الصفوف الزوجية
            if pattern == "staggered" and j % 2 == 1:
                x += x_step / 2.0

            pt = Point(x, y)
            if room.polygon.is_point_inside(pt):
                devices.append(Device(
                    position=pt,
                    device_type=DeviceType.SMOKE_DETECTOR,
                    coverage_radius=spacing / 2
                ))
    return devices


# ============================================================================
# DUCT DETECTORS (Added in V8 PATCH)
# ============================================================================

def suggest_duct_detectors(hvac_ducts):
    """
    يقترح duct detectors لكل duct في نظام HVAC.
    Per NFPA 72 Section 17.7.5:
      - detector عند upstream من كل fan
      - كل 21m (70ft) على امتداد الـ duct
    """
    if hvac_ducts is None:
        raise ValueError("hvac_ducts cannot be None")

    devices = []
    NFPA_MAX_SPACING_M = 21.0

    for duct in hvac_ducts:
        if not hasattr(duct, 'start_x') or not hasattr(duct, 'end_x'):
            # Skip missing coordinates
            continue

        duct_length_m = math.sqrt(
            (duct.end_x - duct.start_x) ** 2 +
            (duct.end_y - duct.start_y) ** 2
        )

        # Detector عند بداية الـ duct (upstream)
        devices.append(Device(
            position=Point(x=duct.start_x, y=duct.start_y, z=getattr(duct, 'height_z', 3.0)),
            device_type=DeviceType.DUCT_DETECTOR,
            coverage_radius=1.0,
            ai_justification=f"Upstream duct detector per NFPA 72 s17.7.5"
        ))

        # Detectors إضافية كل 21m
        num_intervals = int(duct_length_m / NFPA_MAX_SPACING_M)
        for i in range(1, num_intervals + 1):
            ratio = (i * NFPA_MAX_SPACING_M) / duct_length_m
            if ratio >= 1.0:
                break
            pos_x = duct.start_x + ratio * (duct.end_x - duct.start_x)
            pos_y = duct.start_y + ratio * (duct.end_y - duct.start_y)

            devices.append(Device(
                position=Point(x=pos_x, y=pos_y, z=getattr(duct, 'height_z', 3.0)),
                device_type=DeviceType.DUCT_DETECTOR,
                coverage_radius=1.0,
                ai_justification=f"Duct detector at {i*21}m interval per NFPA 72 s17.7.5"
            ))

    return devices
