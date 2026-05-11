"""
auto_placement.py - خوارزمية اقتراح مواقع الأجهزة (شبكة ديناميكية)
الوصف: توزع الأجهزة تلقائياً على كامل طول وعرض الغرفة بناءً على التباعد
       المسموح من المعيار، مع هامش آمن = نصف قطر التغطية.
"""
import math
from typing import List
from src.core.models import Room, Device, DeviceType, Point

def suggest_devices(room: Room, spacing: float) -> List[Device]:
    """
    spacing:قصى مسافة مسموحة بين جهازين (مثلاً 9.1م لـ NFPA 72).
    الهامش من الجدار = spacing / 2 (نصف قطر التغطية القياسي).
    """
    if not room.polygon or not room.polygon.exterior:
        return []

    edge_margin = spacing / 2.0   # <--- هنا السر

    # 1. أبعاد الصندوق المحيط
    coords = [(p.x, p.y) for p in room.polygon.exterior]
    min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
    min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)

    room_width = max_x - min_x
    room_height = max_y - min_y

    # 2. المساحة الفعالة (إذا became 0 أو سالب، نستخدم 0 كهامش)
    eff_w = room_width - 2 * edge_margin
    eff_h = room_height - 2 * edge_margin
    
    # لو المساحة الفعالة سالبة، نستخدم هامش = 0
    if eff_w <= 0:
        eff_w = room_width
        edge_margin = 0.0
    if eff_h <= 0:
        eff_h = room_height
        edge_margin = 0.0

    # 3. عدد الأعمدة والصفوف
    cols = max(1, math.ceil(eff_w / spacing) + 1)
    rows = max(1, math.ceil(eff_h / spacing) + 1)

    # 4. التباعد الفعلي
    x_step = eff_w / (cols - 1) if cols > 1 else 0.0
    y_step = eff_h / (rows - 1) if rows > 1 else 0.0

    # 5. توليد النقاط
    devices = []
    for i in range(cols):
        for j in range(rows):
            x = min_x + edge_margin + i * x_step
            y = min_y + edge_margin + j * y_step
            pt = Point(x, y)
            if room.polygon.is_point_inside(pt):
                devices.append(Device(
                    position=pt,
                    device_type=DeviceType.SMOKE_DETECTOR,
                    coverage_radius=spacing / 2
                ))
    return devices
