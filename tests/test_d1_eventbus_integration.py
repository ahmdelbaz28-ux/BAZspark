"""
tests/test_d1_eventbus_integration.py
======================================

Tests for Stage D / D1 — EventBus integration across fireai/agents,
facp_distributed/l2_orchestrator, and revit_integration/events.

Covers:
  - D1.1: LearningAgent subscribes to ROOM_ANALYSIS_COMPLETE and stores
          experiences.
  - D1.2: PlannerAgent / OptimizerAgent return simulated=True with warning logs.
  - D1.3: EventBusAdapter wraps the real fireai EventBus (publish / subscribe).
"""

from __future__ import annotations

import json
import logging

import pytest

from fireai.agents.learning_agent import LearningAgent
from fireai.core.event_bus import EventBus, Events

# ── D1.1: LearningAgent EventBus integration ──────────────────────────────


class TestLearningAgentEventBusSubscription:
    """LearningAgent should auto-subscribe to ROOM_ANALYSIS_COMPLETE on init."""

    def test_learning_agent_subscribes_on_init(self, tmp_path):
        EventBus.reset()
        db_path = str(tmp_path / "test_learning.sqlite3")
        agent = LearningAgent(db_path=db_path)

        bus = EventBus.instance()
        callbacks = bus._listeners.get(Events.ROOM_ANALYSIS_COMPLETE, [])
        assert len(callbacks) >= 1
        assert agent._on_room_analysis_complete in callbacks

        agent.close()
        EventBus.reset()

    @pytest.mark.parametrize(
        ("success", "nfpa_valid", "expected_outcome"),
        [
            (True, True, "success"),
            (True, False, "partial"),
            (False, True, "failure"),
            (False, False, "failure"),
        ],
    )
    def test_room_analysis_event_stores_experience(
        self, tmp_path, success, nfpa_valid, expected_outcome
    ):
        EventBus.reset()
        db_path = str(tmp_path / "test_learning.sqlite3")
        agent = LearningAgent(db_path=db_path)

        bus = EventBus.instance()
        bus.publish(
            Events.ROOM_ANALYSIS_COMPLETE,
            data={
                "room_id": "R-TEST",
                "success": success,
                "nfpa_valid": nfpa_valid,
                "detector_count": 12,
                "coverage_pct": 0.95,
                "errors": [],
                "warnings_count": 0,
            },
            source="test",
        )

        rows = agent.conn.execute("SELECT outcome, detector_count FROM experiences").fetchall()
        assert len(rows) == 1
        assert rows[0]["outcome"] == expected_outcome
        assert rows[0]["detector_count"] == 12

        agent.close()
        EventBus.reset()

    def test_learning_agent_experience_contains_room_config(self, tmp_path):
        EventBus.reset()
        db_path = str(tmp_path / "test_learning.sqlite3")
        agent = LearningAgent(db_path=db_path)

        bus = EventBus.instance()
        bus.publish(
            Events.ROOM_ANALYSIS_COMPLETE,
            data={
                "room_id": "R-101",
                "success": True,
                "nfpa_valid": True,
                "detector_count": 8,
                "coverage_pct": 0.88,
            },
            source="test",
        )

        row = agent.conn.execute("SELECT room_config FROM experiences").fetchone()
        config = json.loads(row["room_config"])
        assert config["room_id"] == "R-101"

        agent.close()
        EventBus.reset()


# ── D1.2: PlannerAgent / OptimizerAgent simulated flag ─────────────────────


class TestAgentSimulatedFlag:
    """PlannerAgent and OptimizerAgent must mark results as simulated."""

    def test_planner_schedule_returns_simulated(self):
        from facp_distributed.l2_orchestrator.agent_manager import PlannerAgent

        agent = PlannerAgent()
        result = agent.execute_task(
            {
                "method": "schedule.optimize",
                "params": {"payload": {"schedule": {"tasks": ["task1", "task2"]}}},
            }
        )
        assert result["status"] == "success"
        assert result["simulated"] is True
        assert "improvement_percentage" in result["result"]

    def test_optimizer_returns_simulated(self):
        from facp_distributed.l2_orchestrator.agent_manager import OptimizerAgent

        agent = OptimizerAgent()
        result = agent.execute_task(
            {
                "method": "optimize.performance",
                "params": {"payload": {"target": {"parameters": {}}, "goals": ["perf"]}},
            }
        )
        assert result["status"] == "success"
        assert result["simulated"] is True
        assert "improvement_metrics" in result["result"]

    def test_optimizer_goals_are_passed_through(self):
        from facp_distributed.l2_orchestrator.agent_manager import OptimizerAgent

        agent = OptimizerAgent()
        result = agent.execute_task(
            {
                "method": "optimize.performance",
                "params": {"payload": {"target": {"parameters": {}}, "goals": ["latency"]}},
            }
        )
        assert "latency" in result["result"]["goals_addressed"]

    def test_planner_warning_logged(self, caplog):
        from facp_distributed.l2_orchestrator.agent_manager import PlannerAgent

        agent = PlannerAgent()
        with caplog.at_level(
            logging.WARNING, logger="facp_distributed.l2_orchestrator.agent_manager"
        ):
            agent.execute_task(
                {
                    "method": "schedule.optimize",
                    "params": {"payload": {"schedule": {"tasks": []}}},
                }
            )
        assert any("SIMULATED" in r.message for r in caplog.records)

    def test_optimizer_warning_logged(self, caplog):
        from facp_distributed.l2_orchestrator.agent_manager import OptimizerAgent

        agent = OptimizerAgent()
        with caplog.at_level(
            logging.WARNING, logger="facp_distributed.l2_orchestrator.agent_manager"
        ):
            agent.execute_task(
                {
                    "method": "optimize.performance",
                    "params": {"payload": {"target": {}, "goals": []}},
                }
            )
        assert any("SIMULATED" in r.message for r in caplog.records)


# ── D1.3: EventBusAdapter ────────────────────────────────────────────────


class TestEventBusAdapter:
    """EventBusAdapter wraps the real EventBus with an async interface."""

    def test_adapter_uses_singleton_event_bus(self):
        from revit_integration.events.event_publisher import EventBusAdapter

        adapter = EventBusAdapter()
        assert adapter._bus is EventBus.instance()

    @pytest.mark.asyncio
    async def test_adapter_publish_returns_true(self):
        EventBus.reset()
        from revit_integration.events.event_publisher import EventBusAdapter

        adapter = EventBusAdapter()
        event_data = {
            "event_type": "RevitModelImported",
            "payload": {"element_id": "e1", "model_type": "test", "timestamp": "2024-01-01"},
            "source": "test",
        }
        result = await adapter.publish(event_data)
        assert result is True
        EventBus.reset()

    @pytest.mark.asyncio
    async def test_adapter_subscribe_and_receive(self):
        EventBus.reset()
        from revit_integration.events.event_publisher import EventBusAdapter

        adapter = EventBusAdapter()
        received = []

        def handler(data):
            received.append(data)

        await adapter.subscribe("revit.test.event", handler)
        EventBus.instance().publish(
            "revit.test.event",
            data={"msg": "hello"},
            source="test",
        )
        assert received == [{"msg": "hello"}]
        EventBus.reset()

    def test_revit_publisher_uses_adapter_by_default(self):
        from revit_integration.events.event_publisher import EventBusAdapter, RevitEventPublisher

        publisher = RevitEventPublisher()
        assert isinstance(publisher.event_bus, EventBusAdapter)
