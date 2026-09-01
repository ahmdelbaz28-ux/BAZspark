"""backend/tests/test_shared_state.py — Multi-replica Shared State Store tests (S5).

Validates:
1. Cross-process / multi-worker ticket issuance and consumption.
2. Single-use ticket burning.
3. Origin-bound validation.
4. Cluster-wide active agent registration and discovery.
"""

from types import SimpleNamespace

from backend.core.shared_state import SharedStateStore
from backend.database import get_db


def test_shared_ws_ticket_cross_worker_lifecycle():
    db = get_db()
    worker_a = SharedStateStore(db=db)
    worker_b = SharedStateStore(db=db)

    api_key_info = SimpleNamespace(role="engineer", name="tester_alice", email="alice@bazspark.com")
    origin = "http://localhost:5173"

    # Worker A issues ticket
    ticket = worker_a.issue_ws_ticket(api_key_info, origin=origin, ttl_seconds=60)
    assert ticket
    assert isinstance(ticket, str)

    # Worker B consumes ticket
    consumed = worker_b.consume_ws_ticket(ticket, origin=origin)
    assert consumed is not None
    assert consumed.name == "tester_alice"
    assert consumed.role == "engineer"

    # Second consumption on either worker returns None (single-use burned)
    assert worker_a.consume_ws_ticket(ticket, origin=origin) is None
    assert worker_b.consume_ws_ticket(ticket, origin=origin) is None


def test_shared_ws_ticket_origin_mismatch_rejected():
    db = get_db()
    store = SharedStateStore(db=db)
    api_key_info = SimpleNamespace(role="engineer", name="tester_bob", email="bob@bazspark.com")

    ticket = store.issue_ws_ticket(api_key_info, origin="http://localhost:5173", ttl_seconds=60)
    # Origin mismatch
    consumed = store.consume_ws_ticket(ticket, origin="http://attacker.com")
    assert consumed is None


def test_shared_active_agent_cross_worker_discovery():
    db = get_db()
    worker_a = SharedStateStore(db=db)
    worker_b = SharedStateStore(db=db)

    agent_type = "revit"
    # Initially no agent
    # Worker A registers agent
    aid = worker_a.register_active_agent(agent_type)
    assert aid

    # Worker B discovers active agent
    assert worker_b.has_active_agent(agent_type) is True

    # Worker A unregisters agent
    worker_a.unregister_active_agent(aid)
    assert worker_b.has_active_agent(agent_type) is False
