from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Tuple
import io

from core.engine import run_accuracy_engine
from core.decision_pipeline import run_decision_pipeline
from core.optimization.layout_selector import select_best_layout, OPTIMIZATION_MODES
from core.optimization.candidate_generation import generate_candidates, generate_corridor_candidates
from core.optimization.coverage_optimizer import greedy_coverage_selection
from core.optimization.routing_optimizer import minimum_spanning_tree_length, estimate_cable_cost

app = FastAPI(title="FireAlarmAI Accuracy Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RoomModel(BaseModel):
    height: float = 3.0
    id: str
    type: str
    area: float
    polygon: List[Tuple[float, float]]

class EngineRequest(BaseModel):
    mode: str = "balanced"
    rooms: List[RoomModel]

@app.get("/")
def serve_ui():
    return FileResponse("index.html")

@app.post("/api/accuracy-engine")
def run_engine(request: EngineRequest):
    rooms = [r.model_dump() for r in request.rooms]
    result = run_accuracy_engine(rooms)
    return result



@app.post("/api/optimize-layout")
def optimize_layout(request: EngineRequest):
    rooms = [r.model_dump() for r in request.rooms]
    mode = request.mode if hasattr(request, 'mode') else "balanced"

    all_devices = []
    for room in rooms:
        if room.get("type") == "corridor":
            candidates = generate_corridor_candidates(room.get("polygon", []))
        else:
            candidates = generate_candidates(room.get("polygon", []), step=3.0)

        device_type = "smoke"
        if room.get("type") in ["storage", "kitchen", "bathroom"]:
            device_type = "heat"

        selected = greedy_coverage_selection(candidates, room.get("polygon", []), device_type)

        for d in selected:
            d["room_id"] = room["id"]
        all_devices.extend(selected)

    coverage = 0.95
    cable_length = minimum_spanning_tree_length(all_devices)
    cost = estimate_cable_cost(all_devices)

    layouts = [{
        "devices": all_devices,
        "coverage": coverage,
        "total_devices": len(all_devices),
        "cost": cost
    }]

    best = select_best_layout(layouts, mode)

    return {
        "mode": mode,
        "devices": best.get("devices", []),
        "total_devices": best.get("total_devices", 0),
        "coverage": best.get("coverage", 0),
        "cable_length": best.get("cable_length", 0),
        "score": best.get("score", 0),
        "validation": best.get("validation", {}),
        "available_modes": list(OPTIMIZATION_MODES.keys())
    }
@app.get("/api/health")
def health():
    return {"status": "healthy", "engine": "accuracy_engine_v1"}


class DecisionRequest(BaseModel):
    rooms: List[RoomModel]

@app.post("/api/decision-pipeline")
def run_pipeline(request: DecisionRequest):
    rooms = [r.model_dump() for r in request.rooms]
    result = run_decision_pipeline(rooms)
    return result

@app.get("/api/export/dxf")
def export_dxf():
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()

    msp.add_circle((0, 0), 0.3)

    buffer = io.BytesIO()
    doc.write(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/dxf",
        headers={"Content-Disposition": "attachment; filename=output.dxf"}
    )