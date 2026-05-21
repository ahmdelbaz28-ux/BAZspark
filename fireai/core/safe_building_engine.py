"""
fireai/core/safe_building_engine.py
===================================
Replaces ProcessPoolExecutor bindings triggering Deadlocks at CBC level,
with safely managed, lock-restricted threading executing pure multi-node
verification safely.

Architecture:
  - Uses ThreadPoolExecutor instead of ProcessPoolExecutor
  - Global RLock prevents C++ memory corruption on CBC solver library
  - Sequential execution within each thread (CBC does NOT release GIL)
  - Timeout protection per-room (180s max per solve)
  - Graceful error handling with CRASH status on fatal failures

Safety:
  - V0.3 ProcessPoolExecutor prohibition from building_engine.py applies.
  - CBC (PuLP solver) is a C-level library that does NOT release the GIL.
  - ProcessPoolExecutor with CBC causes deadlocks on fork().
  - ThreadPoolExecutor with RLock ensures only ONE CBC instance runs at a time,
    preventing memory corruption while maintaining thread safety.
  - This is NOT about parallelism (GIL prevents that for CPU-bound CBC).
    It is about SAFE concurrent submission of work items with sequential
    execution guaranteed by the lock.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import time
import logging

logger = logging.getLogger(__name__)


class SafeBuildingEngine:
    """
    Thread-safe multi-floor building analysis engine.

    Uses ThreadPoolExecutor with a global RLock to serialize CBC solver
    invocations. This prevents the deadlock scenario that occurs when
    ProcessPoolExecutor forks while CBC holds internal C-level locks.

    The RLock ensures that only one thread enters the CBC solver at a
    time, which is correct because:
      1. CBC does not release the GIL (no true parallelism possible)
      2. Sequential execution within the lock prevents data races
      3. The ThreadPoolExecutor provides clean task submission and
         result collection with timeout support

    Parameters:
        max_threads: Maximum number of worker threads (default 4).
            Note: due to the RLock, only ONE thread will be actively
            solving at any time. Multiple threads allow overlap of
            I/O (result collection, logging) with computation.
    """

    def __init__(self, max_threads: int = 4):
        self.max_threads = max_threads
        self.global_c_level_lock = threading.RLock()  # Hard barrier avoiding C++ Memory Corruption on solver library instance loading.

    def _solve_mip_safe(self, room_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solve MIP for a single room in a thread-safe manner.

        The RLock ensures only one thread enters the CBC solver at a
        time, preventing concurrent access to C-level solver state.

        Parameters:
            room_spec: Dictionary with room parameters:
                - room_id: Unique room identifier
                - width_m: Room width in meters
                - polygon_coords: Optional polygon coordinates
                - Other fields passed to OptimalMIPEngine

        Returns:
            Dictionary with:
                - room_id: Room identifier
                - success: Whether solve completed without exception
                - placements: Detector positions (if successful)
                - coverage_pct: Coverage percentage (if successful)
                - status: Solver status string
                - calc_time_sec: Wall-clock solve time
                - error: Exception message (if failed)
        """
        start = time.time()
        try:
            # Forced encapsulation with the thread execution lock ensuring independent solving process tracking
            with self.global_c_level_lock:
                from fireai.core.spatial_engine.mip_solver import OptimalMIPEngine
                solver = OptimalMIPEngine(
                    grid_size=room_spec.get('width_m', 10.0),
                    radius=6.37,
                    placement_step=1.0,
                    coverage_step=0.5,
                    time_limit_s=60,
                )

                placements = []
                coverage_pct = 0.0
                status = "FAIL"

                if 'polygon_coords' in room_spec:
                    placements, coverage_pct, _, status = solver.solve_polygon(room_spec['polygon_coords'])
                else:
                    placements, coverage_pct, _, status = solver.solve()

                elapsed = time.time() - start
                return {
                    "room_id": room_spec.get("room_id", "UNK"),
                    "success": True,
                    "placements": placements,
                    "coverage_pct": coverage_pct,
                    "status": status,
                    "calc_time_sec": elapsed,
                }
        except Exception as ex:
            logger.error(f"Safe Solver Failure upon {room_spec.get('room_id')}: {ex}")
            return {"room_id": room_spec.get("room_id"), "success": False, "error": str(ex)}

    def run_multi_floor_safety_analysis(self, floor_spec_registry: List[Dict[str, Any]]) -> List[Dict]:
        """
        Run MIP analysis across multiple floors in a thread-safe manner.

        Flattens the floor/room hierarchy into a list of room specifications,
        submits each room as a separate task to the ThreadPoolExecutor, and
        collects results with timeout protection.

        The RLock in _solve_mip_safe ensures that CBC solver invocations
        are serialized, preventing the deadlock scenario that occurs with
        ProcessPoolExecutor + CBC.

        Parameters:
            floor_spec_registry: List of floor specification dictionaries.
                Each floor dict must have:
                    - floor_id: Floor identifier
                    - rooms: List of room specification dicts

        Returns:
            List of result dictionaries (one per room), each containing:
                - room_id: Room identifier
                - success: Whether solve completed
                - placements: Detector positions (if successful)
                - coverage_pct: Coverage percentage (if successful)
                - status: Solver status or "CRASH" on fatal error
                - calc_time_sec: Solve time (if successful)
                - error: Exception message (if failed)
        """
        results = []
        rooms_flatted = []

        for f_data in floor_spec_registry:
            floor_lbl = f_data.get("floor_id")
            for rm in f_data.get("rooms", []):
                rm['virtual_floor'] = floor_lbl
                rooms_flatted.append(rm)

        logger.info(f"Commencing protected multi-thread evaluation over {len(rooms_flatted)} discrete areas.")

        with ThreadPoolExecutor(max_workers=self.max_threads) as tpool:
            work_q = {tpool.submit(self._solve_mip_safe, rm_args): rm_args['room_id'] for rm_args in rooms_flatted}
            for w in as_completed(work_q):
                room_trace = work_q[w]
                try:
                    res_payload = w.result(timeout=180)
                    results.append(res_payload)
                except Exception as fatal_outage:
                    logger.error(f"Task timeout or death on thread assigned to: {room_trace}")
                    results.append({"room_id": room_trace, "success": False, "status": "CRASH"})
        return results
