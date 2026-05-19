"""
twin/ — FireAI Level 4 Digital Twin Engine
============================================

Architecture:
  StateEngine       → Deterministic state management with event sourcing
  NFPA72Bridge      → Bi-directional NFPA 72 calculation interface
  FirePhysics       → Physics-based fire simulation (zone + CFD-lite)
  SimulationLayer   → High-level simulation with detector tracking + NFPA 72
  AuditEventStore   → WAL-backed immutable event log with SHA-256 hash chain

Safety Classification:
  ⚠️  This module implements SIMPLIFIED fire physics, NOT full CFD.
  ⚠️  All simulation results must be verified by a licensed PE.
  ⚠️  Never use simulation output as the sole basis for life-safety decisions.

Known Limitations (documented, not hidden):
  1. Navier-Stokes uses fractional-step (cross-advection fixed in V2)
  2. Smoke transport uses turbulent diffusivity (CFAST-calibrated)
  3. No radiation heat transfer model
  4. Multi-zone uses 2-layer zone model (not full CFD)
  5. Detector model uses probabilistic noise (LCG PRNG, not crypto-grade)
  6. No HVAC coupling (future enhancement)
  7. No structural response modeling

Bug Fixes Applied (from Consultant Code Review 2026-05-19):
  BUG 3: Timer-based detector checking (not int(t) % 30) → simulation_layer.py
  BUG 4: Proper lower-layer temperature with plume impact → simulation_layer.py
  BUG 5: Grid-based coverage + ceiling height adjustment → nfpa72_bridge.py
  BUG FIX: det.x → det.y for y-axis wall distance → nfpa72_bridge.py line 310

Digital Twin Level: 4 (Physics-based multi-domain)
"""
