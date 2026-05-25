# FireAI Core Strengthening & Performance Optimization — Consultant Brief

## 1. PROJECT OVERVIEW

**Project:** FireAI — A safety-critical fire alarm system design plugin for Autodesk Revit  
**Domain:** Fire protection engineering (NFPA 72, NEC, IBC compliance)  
**Language:** Python 3.12  
**Codebase:** ~120K lines of production code (excluding tests)  
**Repository:** GitHub — branch `main`  
**Current Version:** V29  
**Safety Classification:** LIFE-SAFETY CRITICAL — every optimization must preserve correctness

The system receives architectural data (DXF/DWG/IFC/JSON), extracts room geometry, places fire/smoke detectors per NFPA 72 rules, verifies coverage, routes cables per NEC, and generates compliance reports with cryptographic proof chains.

---

## 2. ARCHITECTURE (Exact File Paths & Class Names)

```
/home/z/my-project/revit/
├── core/                              # Root-level core (data models + database)
│   ├── models.py                      # Point3D, Geometry, UniversalElement, Room, Device, Violation, Obstruction
│   ├── database.py                    # UniversalDataModel (SQLite-backed CRUD)
│   ├── geometry_kernel.py             # Point2D, Polygon2D (ray-casting, Shapely bridge)
│   ├── truth_deriver.py               # NFPAConstraintModel, derive_truth() — O(grid×devices×obstructions)
│   ├── code_compliance_engine.py      # CodeComplianceEngine, NECCompliance
│   ├── cognitive_kernel.py            # CognitiveKernel, BOQComparator (SQLite audit)
│   ├── floor_orchestrator.py          # FloorOrchestrator — per-room MIP solve
│   ├── multi_floor_analyzer.py        # MultiFloorAnalyzer — O(n²) building distances
│   ├── adaptive_solver.py             # AdaptiveSolver — Shapely exclusion zones
│   ├── engineering_router.py          # EngineeringRouter — A* on visibility graph
│   ├── electrical_ceiling_analyzer.py # ElectricalCeilingAnalyzer
│   ├── room_classifier.py             # RuleBasedRoomClassifier
│   ├── safety_gates.py                # Safety gate checks
│   ├── truth_model.py                 # TruthState (deprecated)
│   └── ... (24 files total)
│
├── parsers/                           # Input parsing layer
│   ├── dwg_parser.py                  # DWGParser with extract_rooms_from_chaos() + _assemble_closed_polygons()
│   ├── dxf_parser.py                  # DXFParser (ezdxf-based)
│   ├── ifc_parser.py                  # IFCParser (ifcopenshell-based)
│   ├── pdf_parser.py                  # PDFParser (PyMuPDF-based)
│   └── ... (13 files total)
│
├── fireai/core/                       # Main computation engines (~80 files)
│   ├── spatial_engine/
│   │   ├── density_optimizer.py       # DensityOptimizer — 5 placement strategies + NumPy verification
│   │   ├── mip_solver.py             # MIP optimization via PuLP
│   │   ├── exact_coverage.py         # ExactCoverageEngine — Shapely unary_union + difference
│   │   ├── analytical_verifier.py    # AnalyticalVerifier — O(D²) midpoint checks
│   │   ├── voronoi_verifier.py       # VoronoiVerifier — scipy.spatial.Voronoi
│   │   ├── consensus_engine.py       # ConsensusEngine — 3-verifier aggregation
│   │   └── proof_certificate.py      # ProofCertificateGenerator — SHA-256 proof
│   │
│   ├── nfpa72_calculations.py         # NFPA 72 Table 17.6.3.1.1 lookup, radius/spacing calculations
│   ├── nfpa72_models.py              # CeilingSpec, RoomSpec, DetectorPlacement, CoverageResult
│   ├── nfpa72_coverage.py            # Coverage verification (Shapely-based)
│   ├── nfpa72_technology_dispatcher.py # EliteTechnologyDispatcher
│   ├── digital_twin.py               # DigitalTwin — thread-safe lifecycle, drift, simulation
│   ├── building_engine.py            # BuildingEngine — top-level orchestrator
│   ├── floor_analyser.py             # FloorAnalyser — per-room DensityOptimizer
│   ├── fireai_core.py                # FireAISystem — main entry point
│   ├── acoustic_calculator.py        # AcousticSPLCalculator — SPL, reverberation, speaker placement
│   ├── scenario_engine.py            # ScenarioRunner, FirePhysics
│   ├── semi_cfast_engine.py          # Semi-empirical CFAST zone model
│   ├── aset_rset_calculator.py       # ASET/RSET validation
│   ├── hybrid_survivability.py       # HybridSurvivabilityEngine
│   ├── auto_drafting_engine.py       # AutoDraftingEngine — A* cable routing + DXF output
│   ├── monte_carlo.py                # Monte Carlo fire scenario sampling
│   ├── flame_detector_aoc_raytrace.py # FlameDetectorAOCRayTrace — ray casting
│   ├── ugld_raytrace.py             # Ultrasonic gas leak detection raytracing
│   ├── ugld_acoustics.py            # Acoustic propagation modeling
│   ├── polygon_optimizer.py          # PolygonDensityOptimizer — non-rectangular rooms
│   ├── routing_engine_v10.py         # EliteClassARouter — Class A circuit routing
│   ├── routing_global_class_a.py     # EliteGlobalRouter — multi-floor routing
│   ├── pathway_survivability_engine.py # PathwaySurvivabilityEngine — NFPA 72 Ch.12
│   ├── conduit_fill_analyzer.py      # ConduitSizer — NEC fill calculations
│   ├── battery_aging_derating.py     # BatteryAuditor — thermal/aging models
│   ├── slc_capacitance.py            # SLCCapacitanceAuditor — SLC loop verification
│   ├── event_bus.py                  # EventBus — singleton pub/sub
│   ├── audit_store.py                # AuditStore — SQLite + SHA-256 hash chain
│   ├── delta_cache.py                # DeltaCache — LRU incremental change detection
│   ├── evidence_chain.py             # EvidenceChain — cryptographic proof
│   ├── safety_assurance.py           # SafetyTier, FailSafeRule, OverrideRole
│   ├── parameter_optimizer.py        # ParameterOptimizer — grid search
│   └── ... (~50 more files)
│
├── validation/                        # Compliance validation layer
│   ├── compliance_oracle.py          # ComplianceOracle — 5-step verification pipeline
│   └── ...
│
└── tests/                             # ~90 test files, 434+ tests
```

---

## 3. CURRENT PERFORMANCE BASELINE (Measured)

All measurements taken on the production server, Python 3.12, single-threaded:

| Operation | Throughput | Latency/Call | Bottleneck |
|-----------|-----------|--------------|------------|
| `Geometry.calculate_area()` (4-vertex rect) | 714K/sec | 1.40 µs | Object allocation (61%) |
| `Geometry.calculate_area()` (reuse objects) | 1.6M/sec | 0.63 µs | Pure computation |
| `Geometry.calculate_perimeter()` (reuse) | 775K/sec | 1.29 µs | `distance_to()` method overhead |
| `Point3D()` object creation | 1.2M/sec | 0.86 µs | Dataclass `__init__` |
| `Point3D.distance_to()` | 6.3M/sec | 0.16 µs | Efficient |
| `_assemble_closed_polygons()` 10K rooms | 37K rooms/sec | 27 µs/room | ✅ Already optimized (V29) |
| `UniversalDataModel.add_element()` | 2.9K/sec | 340 µs | **SQLite open/close per call** |
| Shapely `Polygon.area` | 74K/sec | 13.5 µs | **21× slower than pure Python** |
| numpy area (with Point3D→array conversion) | 222K/sec | 4.5 µs | **7× slower than pure Python for N<50** |

### Key Finding: numpy is SLOWER for small polygons (4-8 vertices)
Pure Python shoelace (0.63 µs) beats numpy with conversion (4.5 µs) by 7×. numpy only wins for polygons with 50+ vertices.

---

## 4. IDENTIFIED BOTTLENECKS (Ranked by Impact)

### 🔴 CRITICAL — Must Fix

#### B1: `UniversalDataModel._persist_element()` — SQLite Connection-per-Write Anti-Pattern
- **File:** `core/database.py`, method `_persist_element()`
- **Bug:** Every `add_element()` / `update_element()` / `delete_element()` call opens a NEW `sqlite3.connect()`, INSERTs, commits, and CLOSES the connection.
- **Additional Bug:** When `db_path=":memory:"`, `_init_database()` creates tables on connection A, but `_persist_element()` opens connection B — `:memory:` databases are connection-scoped, so all writes silently fail.
- **Impact:** 340 µs/call. With connection pooling + batch writes: estimated 5-10 µs/call (34-68× improvement).
- **Fix Needed:**
  1. Hold a single persistent `self._conn` open for the lifetime of the `UniversalDataModel` instance
  2. Add `add_elements_batch(elements: list, batch_size=1000)` using `executemany()` within a single transaction
  3. Fix `:memory:` mode to use `file::memory:?cache=shared` URI or the same connection

#### B2: `truth_deriver.derive_truth()` — O(grid × devices × obstructions) Shapely Hell
- **File:** `core/truth_deriver.py`, method `derive_truth()`
- **Problem:** For every grid point (0.25m spacing), for every device, for every obstruction, creates a `shapely.LineString` and calls `.intersects()`. This is O(G × D × O) Shapely operations.
- **Impact:** For a 100m² room with 5 devices and 3 obstructions: ~2000 grid points × 5 × 3 = 30,000 Shapely LineString operations. For 10,000 rooms: 300 million Shapely calls.
- **Fix Needed:**
  1. Pre-compute Shapely geometry once per device and obstruction (not per grid point)
  2. Use spatial indexing (STRtree or grid) to skip grid points clearly inside/outside coverage
  3. Consider vectorized NumPy approach for grid-point-to-device distance (skip Shapely entirely for simple cases)
  4. Early termination: if a grid point is already covered, skip remaining devices

#### B3: `ExactCoverageEngine.verify()` — Shapely `unary_union` + `difference` on N Circles
- **File:** `fireai/core/spatial_engine/exact_coverage.py`, method `verify()`
- **Problem:** Creates `Point.buffer(R)` Shapely circle for each detector, then `unary_union()` to merge all circles, then `room_polygon.difference(coverage_union)` to find blind spots.
- **Impact:** Shapely polygon union is O(N log N) per call, but for large N (100+ detectors in a building), this becomes expensive. Also, `difference()` on complex polygons can be O(N²) in worst case.
- **Fix Needed:**
  1. Use `shapely.union()` (new fast union in Shapely 2.x) or `shapely.coverage_union()` for better performance
  2. Skip exact verification when analytical verifier already confirms 100% coverage
  3. Consider hierarchical approach: verify per-room first, then global

### 🟡 HIGH — Should Fix

#### B4: `DensityOptimizer._remove_redundant()` — O(n² × k) Coverage Matrix
- **File:** `fireai/core/spatial_engine/density_optimizer.py`, method `_remove_redundant()`
- **Problem:** For each detector, builds a grid×detector coverage matrix, then greedily removes detectors whose removal doesn't create coverage gaps. Re-verifies after each removal.
- **Impact:** For a room with 20 detectors and 10,000 grid points: 200,000 coverage checks per removal attempt.
- **Fix Needed:** Use the spatial grid index approach (already proven in V29 `_assemble_closed_polygons`) for O(1) neighbor lookup instead of O(n) per grid point.

#### B5: `EngineeringRouter._find_path_astar()` — O(V²) Visibility Graph
- **File:** `core/engineering_router.py`, method `_find_path_astar()`
- **Problem:** Builds full visibility graph with `LineString.intersects()` for every pair of vertices. For N obstacles with M vertices each: O((N×M)²) Shapely intersection checks.
- **Fix Needed:** Lazy visibility graph construction — only compute edges when A* actually visits a node. Use Shapely `STRtree` for spatial indexing of obstacles.

#### B6: `spatial_field_engine.evaluate_compliance()` — O(grid × devices × obstructions)
- **File:** `validation/spatial_field_engine.py` (or similar)
- **Problem:** Same pattern as truth_deriver: nested loops with Shapely operations per grid point.
- **Fix Needed:** Same as B2 — vectorized distance calculations + spatial indexing.

#### B7: `UniversalElement.to_dict()` Called 3× Per `add_element()`
- **File:** `core/database.py`, method `add_element()`
- **Problem:** `add_element()` calls `to_dict()` for: (1) element_snapshots, (2) add_change_log_entry → to_dict() for new_value, (3) _persist_element → to_dict() for JSON serialization. Each call serializes the entire object graph including geometry points.
- **Fix Needed:** Compute `to_dict()` once, cache the result, pass it to all three consumers.

### 🟢 MEDIUM — Nice to Have

#### B8: `Point3D` Without `__slots__`
- **File:** `core/models.py`, class `Point3D`
- **Problem:** Dataclass without `__slots__` — each instance uses a `__dict__` (~112 bytes overhead vs ~48 bytes with `__slots__`). For 1M rooms with 4 points each = 4M Point3D instances = ~256MB extra memory.
- **Fix Needed:** Add `__slots__ = ('x', 'y', 'z')` to `Point3D` dataclass (Python 3.10+ supports `__slots__` in dataclasses). Must verify all `Point3D` usage patterns are compatible.

#### B9: `Geometry.calculate_perimeter()` Method Call Overhead
- **File:** `core/models.py`, method `calculate_perimeter()`
- **Problem:** Calls `self.points[i].distance_to(self.points[i+1])` per edge. Python method dispatch overhead for each call.
- **Fix Needed:** Inline the distance calculation: `((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5` within the loop, or use `zip(points, points[1:])` iterator.

#### B10: `AnalyticalVerifier._check_midpoints()` — O(D²) Pairwise
- **File:** `fireai/core/spatial_engine/analytical_verifier.py`, method `_check_midpoints()`
- **Problem:** Checks every pair of detectors for uncovered midpoints. O(D²/2) distance calculations.
- **Fix Needed:** Use spatial index (same as V29 grid index) for O(D) neighbor checks instead of O(D²) pairwise.

---

## 5. KEY DATA STRUCTURES (Must Match Exactly)

### core/models.py

```python
@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0
    
    def distance_to(self, other: 'Point3D') -> float:
        return ((self.x - other.x)**2 + 
                (self.y - other.y)**2 + 
                (self.z - other.z)**2) ** 0.5

@dataclass
class Geometry:
    points: List[Point3D]
    polyline_closed: bool = False
    area: float = 0.0
    perimeter: float = 0.0
    
    def calculate_area(self) -> float:
        # Shoelace formula — O(n)
        if len(self.points) < 3:
            return 0.0
        area = 0.0
        for i in range(len(self.points) - 1):
            area += self.points[i].x * self.points[i+1].y
            area -= self.points[i+1].x * self.points[i].y
        self.area = abs(area) / 2.0
        return self.area

@dataclass
class UniversalElement:
    element_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    properties: Optional[SemanticProperties] = None
    geometry: Optional[Geometry] = None
    relationships: List[Relationship] = field(default_factory=list)
    # ... (12 more fields)
```

### core/database.py

```python
class UniversalDataModel:
    def __init__(self, db_path: str = "fireai_universal.db"):
        self.db_path = db_path
        self.elements: Dict[str, UniversalElement] = {}      # In-memory cache
        self.relationships: List[Relationship] = []
        self.conflicts: Dict[str, Conflict] = {}
        self.version = 0
        self.element_snapshots: Dict[str, Dict] = {}
        self._init_database()  # Creates SQLite tables
    
    def _persist_element(self, element: UniversalElement):
        # CURRENT: opens/closes connection per call — BOTTLENECK
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO elements ...', (...))
        conn.commit()
        conn.close()
```

### parsers/dwg_parser.py (V29 Spatial Index — Already Optimized)

```python
@staticmethod
def _assemble_closed_polygons(lines: list, tolerance: float = 0.01) -> list:
    # V29: O(n) spatial grid index with 3×3 Moore neighbourhood
    cell_size = tolerance
    grid_start: dict = {}  # {(cx,cy): set(line_indices)}
    grid_end: dict = {}
    
    for idx, (start, end) in enumerate(lines):
        cs = (int(math.floor(sx / cell_size)), int(math.floor(sy / cell_size)))
        ce = (int(math.floor(ex / cell_size)), int(math.floor(ey / cell_size)))
        grid_start.setdefault(cs, set()).add(idx)
        grid_end.setdefault(ce, set()).add(idx)
    
    # Chain greedily using _find_neighbours(px, py) — checks 9 cells only
    # 10K rooms (40K LINEs) in 0.27s — 230× faster than previous O(n²)
```

### fireai/core/spatial_engine/density_optimizer.py

```python
class DensityOptimizer:
    MAX_SPACING_M = 9.1
    DETECTOR_RADIUS = 6.37
    VERIFY_STEP = 0.20       # Fine verification grid (meters)
    COARSE_STEP = 1.00       # Coarse verification grid (meters)
    PLACEMENT_MARGIN = VERIFY_STEP * math.sqrt(2) / 2  # ≈ 0.1414m
    
    def __init__(self, max_spacing=9.1, wall_min=0.10, radius=6.37):
        self.R = radius
        self.R_place = self.R - self.PLACEMENT_MARGIN  # Conservative placement radius
    
    def optimize(self, room: Room, coverage_radius=None) -> DetectorLayout:
        # Runs 5 strategies: hexG_x, hexG_y, hexA_x, hexA_y, rect_best
        # Picks best by coverage, then proof_valid, then detector count
        # Each strategy places detectors then calls _verify_fast()
    
    def _verify_fast(self, layout: DetectorLayout) -> None:
        # Two-pass hierarchical NumPy verification:
        # Pass 1: Coarse grid (1m) — quick rejection
        # Pass 2: Fine grid (0.2m) on failed cells only — δ-conservative R_eff
        # Uses NumPy broadcasting: corners[n_cells, 4, 2] vs detectors[n_dets, 2]
```

---

## 6. DEPENDENCIES & CONSTRAINTS

### Available Libraries
- Python 3.12
- numpy 2.1.3 ✅
- shapely 2.1.2 ✅
- scipy (Voronoi) ✅
- ezdxf (DXF parsing) ✅
- ifcopenshell (IFC parsing) ✅
- PuLP (MIP solver) ✅

### Safety Constraints (NON-NEGOTIABLE)
1. **Never modify test files** — fix production code only
2. **Conservative interpretation rule** — when in doubt, place MORE detectors, not fewer
3. **Every change must be committed to GitHub** with commit hash + link
4. **No fabricated results** — report exact measurements, never approximate upward
5. **Failed test = fix SOURCE CODE, not the test**
6. **All optimizations must produce identical or more conservative results** — if an optimization changes detector count, it must place MORE detectors, not fewer
7. **Shapely operations must produce bit-identical results** after optimization — floating point reordering is acceptable but geometric outcomes must match

### Code Style
- Arabic comments and docstrings are intentional (bilingual project)
- Type hints are used throughout
- Dataclasses for all data structures
- `@lru_cache` on pure calculation functions
- `threading.RLock` on thread-safe classes (DigitalTwin)
- SHA-256 hashing for audit trails and proof certificates

---

## 7. DELIVERABLES REQUESTED

For each bottleneck (B1–B10), provide:

### A. Production Code Fix
- Exact file path
- Exact method/class to modify
- Complete replacement code (not snippets)
- All imports needed
- Performance measurement script showing before/after

### B. Performance Verification
- Micro-benchmark: 1M iterations for hot-path methods
- Macro-benchmark: 10,000-room building stress test
- Memory profiling for batch operations
- Comparison table: old throughput vs new throughput

### C. Safety Verification
- Run existing test suite: `python -m pytest tests/test_impossibility_protocol.py tests/test_chaos_penetration.py tests/test_event_horizon.py tests/test_safety_critical.py tests/test_basic_functionality.py tests/test_v8_core.py tests/test_v9_integration.py -v`
- Confirm zero test regressions
- For database changes: verify `:memory:` mode works correctly
- For spatial changes: verify identical geometric results

### D. New Batch/Vectorized APIs (Where Applicable)
For modules that currently process one room/element at a time:
- Add `*_batch()` methods that process N items with vectorized NumPy operations
- Maintain backward compatibility with existing single-item methods
- Example: `Geometry.calculate_area_batch(geometries: List[Geometry]) -> List[float]`

---

## 8. PRIORITY ORDER

Fix in this exact order (highest impact first):

1. **B1** — Database connection pooling + batch writes (34-68× improvement on CRUD)
2. **B2** — truth_deriver vectorized grid verification (largest theoretical speedup)
3. **B3** — ExactCoverageEngine Shapely optimization
4. **B7** — to_dict() caching in add_element()
5. **B4** — DensityOptimizer._remove_redundant() spatial index
6. **B5** — EngineeringRouter lazy visibility graph
7. **B6** — spatial_field_engine vectorized compliance
8. **B8** — Point3D __slots__
9. **B9** — Geometry.calculate_perimeter() inline
10. **B10** — AnalyticalVerifier spatial index for midpoint checks

---

## 9. STRESS TEST TARGET

After all optimizations, the system must handle:
- **1,000,000 rooms** × **100 floors** in under 10 minutes (end-to-end pipeline)
- **100,000 element CRUD operations** in under 30 seconds
- **50,000 LINE entities** → polygon assembly in under 5 seconds
- **Zero NaN/Inf leaks** under 50% poison rate
- **100% proof_valid** rate across all rooms

Current capability: ~500 rooms in 30 seconds (single-process density optimization). Target: **2000× throughput improvement**.

---

## 10. ARCHITECTURE DECISIONS NEEDED

The consultant should also advise on:

1. **Should we introduce a C extension (via Cython or pyo3) for the hot-path shoelace/perimeter calculations?** Currently pure Python is fastest for N<50, but C would be 10-50× faster. Trade-off: build complexity vs performance.

2. **Should we replace Shapely operations with GEOS direct calls?** Shapely 2.x wraps GEOS, but the Python overhead per call is ~5 µs. Direct C++ GEOS calls via pygeos or cython could eliminate this.

3. **Should we introduce multiprocessing for per-room optimization?** `DensityOptimizer.optimize()` is embarrassingly parallel across rooms. Current single-process: ~2 rooms/sec. With 8 cores: theoretical 16 rooms/sec.

4. **Should we switch the database layer from SQLite to an in-memory-only architecture with optional persistence?** The SQLite per-element write overhead dominates CRUD. An in-memory dict with periodic WAL-style snapshots could be 100× faster.

5. **Should we pre-compute and cache NFPA 72 radius/spacing tables as NumPy arrays?** Currently uses `@lru_cache(128)` on `calculate_smoke_detector_radius()`. A pre-built lookup array would eliminate function call overhead.

---

## 11. WHAT WE NEED TO MOVE TO THE NEXT STAGE

After the core strengthening is complete, we need the following capabilities to advance to production deployment:

1. **Real-time DWG streaming** — Process 100MB+ DWG files without loading entire file into memory
2. **Incremental recomputation** — When a single room changes, recompute only that room + affected cable routes (not the entire building)
3. **Distributed computation** — Multi-machine processing for buildings with 10,000+ rooms
4. **Plugin API stability** — Freeze the public API so Revit plugin development can proceed
5. **Benchmark suite** — Automated CI benchmark that fails PRs with >5% performance regression

Please provide concrete, production-ready code for all deliverables. Every function must have type hints, docstrings, and be immediately testable by running the existing test suite plus the provided stress test.
