"""
ETAP-AI-WORK Revit Integration Event Publisher
=============================================

Event publisher for publishing Revit integration events to the EventBus.

Principal Software Architect: Eng. Ahmed Elbaz
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any


class EventBusAdapter:
    """Async-compatible adapter over the synchronous fireai.core EventBus.

    The Revit integration layer was built around an async MockEventBus interface
    (``async publish`` / ``async subscribe`` returning ``bool``).  The real
    fireai EventBus is synchronous by design (predictable ordering, no event-loop
    dependency).  This adapter bridges the gap:

    * ``publish`` — wraps the sync ``EventBus.publish`` in an async method
      so ``await publisher._publish_to_bus(...)`` continues to work.
    * ``subscribe`` — wraps async handlers in a sync callback suitable for
      the EventBus.  If an event loop is running the handler is scheduled as a
      task; otherwise it is invoked inline (sync handlers) or skipped with a
      debug log (async handlers without a loop).
    """

    def __init__(self) -> None:
        from fireai.core.event_bus import EventBus

        self.logger = logging.getLogger(__name__)
        self._bus = EventBus.instance()
        self.subscribers: dict[str, list[Any]] = {}

    async def publish(self, event_data: dict[str, Any]) -> bool:
        """
        Publish an event to the fireai EventBus.

        Args:
            event_data: Event payload dict (includes event_type, payload, source, ...).

        Returns:
            bool: True if published successfully.
        """
        try:
            event_type = event_data.get("event_type", "")
            self._bus.publish(
                event_type=event_type,
                data=event_data,
                source=event_data.get("source", "revit_integration"),
            )
            return True
        except Exception as e:
            self.logger.error(f"Error publishing to EventBus: {e}")
            return False

    async def subscribe(self, event_type: str, handler: Callable[[Any], Any]) -> bool:
        """
        Subscribe to an event type on the fireai EventBus.

        Wraps async handlers in a sync callback compatible with the
        EventBus's synchronous dispatch model.

        Args:
            event_type: The event type string to subscribe to.
            handler: Callable invoked when the event fires.

        Returns:
            bool: True if subscription was successful.
        """

        def _sync_callback(event: Any) -> None:
            data = event.data if hasattr(event, "data") else event
            if asyncio.iscoroutinefunction(handler):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(handler(data))
                except RuntimeError:
                    self.logger.debug(
                        "No running event loop; async handler for %s not scheduled", event_type
                    )
            else:
                handler(data)

        # Keep a reference so callers can inspect / manage subscriptions
        self.subscribers.setdefault(event_type, []).append(_sync_callback)
        self._bus.subscribe(event_type, _sync_callback)
        self.logger.info(f"Subscribed to event: {event_type}")
        return True


from .event_definitions import (
    EVENT_PRIORITIES,
    REVIT_EVENT_TYPES,
    validate_event_payload,
)


class RevitEventPublisher:
    """
    Publisher for Revit integration events.
    Integrates with the existing ETAP EventBus system.
    """

    def __init__(self, event_bus_connection=None):
        self.logger = logging.getLogger(__name__)
        self.event_bus = event_bus_connection
        self.published_events = []
        self.failed_events = []

        # Initialize event bus connection if not provided
        if self.event_bus is None:
            self.event_bus = self._initialize_event_bus()

    def _initialize_event_bus(self):
        """
        Initialize connection to the fireai EventBus.

        D1.3: Returns an EventBusAdapter wrapping the real
        fireai.core.event_bus.EventBus singleton instead of a mock.
        """
        self.logger.info("Initializing EventBus adapter for Revit integration")
        return EventBusAdapter()

    async def publish_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        """
        Publish an event to the EventBus.

        Args:
            event_type: type of event (as string)
            payload: Event payload data

        Returns:
            bool: True if event was published successfully
        """
        # Convert string event type to enum
        if event_type in REVIT_EVENT_TYPES:
            event_enum = REVIT_EVENT_TYPES[event_type]
        else:
            self.logger.error(f"Unknown event type: {event_type}")
            return False

        # Validate payload
        validation_errors = validate_event_payload(event_enum, payload)
        if validation_errors:
            self.logger.error(f"Event validation failed: {validation_errors}")
            return False

        # Add timestamp if not present
        if "timestamp" not in payload:
            payload["timestamp"] = datetime.now(UTC).isoformat()

        # Add event metadata
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": payload["timestamp"],
            "source": "revit_integration",
            "priority": EVENT_PRIORITIES.get(event_enum, 0),
        }

        try:
            # Publish to EventBus via the adapter
            success = await self._publish_to_bus(event_data)

            if success:
                self.published_events.append(event_data)
                self.logger.debug(f"Published event: {event_type}")

                # Publish specific event handlers
                await self._handle_specific_event(event_type, payload)
            else:
                self.failed_events.append(event_data)
                self.logger.error(f"Failed to publish event: {event_type}")

            return success

        except Exception as e:
            self.logger.error(f"Error publishing event {event_type}: {e}")
            self.failed_events.append(event_data)
            return False

    async def _publish_to_bus(self, event_data: dict[str, Any]) -> bool:
        """
        Publish event to the EventBus (via the adapter).

        Args:
            event_data: Event data to publish

        Returns:
            bool: True if published successfully
        """
        # Delegate to the adapter, which wraps the synchronous EventBus
        return await self.event_bus.publish(event_data)

    async def _handle_specific_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Handle specific event types with custom logic.

        Args:
            event_type: type of event
            payload: Event payload
        """
        if event_type == "RevitElementImported":
            await self._handle_element_imported(payload)
        elif event_type == "RevitTopologyChanged":
            await self._handle_topology_changed(payload)
        elif event_type == "ElectricalAssetSynced":
            await self._handle_electrical_asset_synced(payload)
        elif event_type == "RevitSyncCompleted":
            await self._handle_sync_completed(payload)

    async def _handle_element_imported(self, payload: dict[str, Any]) -> None:
        """Handle element imported event."""
        element_id = payload.get("element_id", "unknown")
        category = payload.get("category", "unknown")
        target_model = payload.get("target_model", "unknown")

        self.logger.info(
            f"Element imported: {element_id} (Category: {category}, Model: {target_model})"
        )

        # In a real implementation, this might trigger additional processing
        # based on the element type and target model

    async def _handle_topology_changed(self, payload: dict[str, Any]) -> None:
        """Handle topology changed event."""
        element_id = payload.get("element_id", "unknown")
        model_type = payload.get("model_type", "unknown")
        change_type = payload.get("change_type", "unknown")

        self.logger.info(f"Topology changed: {element_id} ({change_type}) in {model_type}")

        # This could trigger electrical analysis updates
        if model_type == "ElectricalModel":
            await self._trigger_electrical_analysis(element_id)

    async def _handle_electrical_asset_synced(self, payload: dict[str, Any]) -> None:
        """Handle electrical asset synced event."""
        element_id = payload.get("element_id", "unknown")
        asset_type = payload.get("asset_type", "unknown")
        name = payload.get("name", "unnamed")

        self.logger.info(f"Electrical asset synced: {name} ({asset_type}) - ID: {element_id}")

        # This could trigger asset-specific processing
        await self._process_electrical_asset(element_id, asset_type)

    async def _handle_sync_completed(self, payload: dict[str, Any]) -> None:
        """Handle sync completed event."""
        successful = payload.get("successful_elements", 0)
        failed = payload.get("failed_elements", 0)
        total = payload.get("total_elements", 0)

        self.logger.info(f"Sync completed: {successful} successful, {failed} failed, {total} total")

        # Trigger any post-sync operations
        await self._post_sync_operations()

    async def _trigger_electrical_analysis(self, element_id: str) -> None:
        """Trigger electrical analysis for affected element."""
        self.logger.debug(f"Triggering electrical analysis for element: {element_id}")
        # In a real implementation, this would trigger load flow or other electrical analyses

    async def _process_electrical_asset(self, element_id: str, asset_type: str) -> None:
        """Process electrical asset based on its type."""
        self.logger.debug(f"Processing electrical asset: {element_id} ({asset_type})")
        # In a real implementation, this would process the asset based on its type

    async def _post_sync_operations(self) -> None:
        """Perform operations after sync completion."""
        self.logger.debug("Performing post-sync operations")
        # In a real implementation, this might trigger validation, reporting, etc.

    async def subscribe_to_event(self, event_type: str, handler: Callable[[Any], Any]) -> bool:
        """
        Subscribe to an event type.

        Args:
            event_type: type of event to subscribe to
            handler: Handler function to call when event occurs

        Returns:
            bool: True if subscription was successful
        """
        try:
            return await self.event_bus.subscribe(event_type, handler)
        except Exception as e:
            self.logger.error(f"Error subscribing to event {event_type}: {e}")
            return False

    async def get_published_events(self) -> list[dict[str, Any]]:
        """Get list of published events."""
        return self.published_events.copy()

    async def get_failed_events(self) -> list[dict[str, Any]]:
        """Get list of failed events."""
        return self.failed_events.copy()

    async def get_event_stats(self) -> dict[str, Any]:
        """Get statistics about published events."""
        total = len(self.published_events) + len(self.failed_events)
        return {
            "published_count": len(self.published_events),
            "failed_count": len(self.failed_events),
            "success_rate": len(self.published_events) / total if total > 0 else 0.0,
        }

    async def flush_events(self) -> None:
        """Flush all pending events."""
        # In a real implementation, this would flush the event queue
        self.logger.debug("Flushing event queue")


class MockEventBus:
    """
    Mock EventBus for development purposes.

    .. deprecated::
        Use :class:`EventBusAdapter` instead.  This class is kept for
        backward-compatibility with tests that explicitly inject a mock.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.subscribers = {}
        self.event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.running = False
        # Strong refs to background tasks so the event loop doesn't GC them
        # before completion (fixes SonarCloud python:S7502).
        self._background_tasks: set = set()

    async def publish(self, event_data: dict[str, Any]) -> bool:
        """
        Publish an event to the mock bus.

        Args:
            event_data: Event data to publish

        Returns:
            bool: True if published successfully
        """
        try:
            # Add to event queue
            await self.event_queue.put(event_data)

            # Notify subscribers if any
            event_type = event_data["event_type"]
            if event_type in self.subscribers:
                for handler in self.subscribers[event_type]:
                    try:
                        # Run handler in background. Keep a strong reference so
                        # the task is not garbage-collected before completion
                        # (SonarCloud python:S7502). The done callback removes
                        # the ref to avoid unbounded growth.
                        task = asyncio.create_task(handler(event_data))
                        self._background_tasks.add(task)
                        task.add_done_callback(self._background_tasks.discard)
                    except Exception as e:
                        self.logger.error(f"Error in event handler: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Error publishing to mock event bus: {e}")
            return False

    async def subscribe(self, event_type: str, handler: Callable[[Any], Any]) -> bool:
        """
        Subscribe to an event type.

        Args:
            event_type: type of event to subscribe to
            handler: Handler function

        Returns:
            bool: True if subscription was successful
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        self.subscribers[event_type].append(handler)
        self.logger.info(f"Subscribed to event: {event_type}")
        return True

    async def start_processing(self):
        """Start processing events from the queue."""
        self.running = True
        while self.running:
            try:
                event_data = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                self.logger.debug(f"Processing event: {event_data['event_type']}")
                self.event_queue.task_done()
            except TimeoutError:
                continue  # Continue waiting for events
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")

    async def stop_processing(self):
        """Stop processing events."""
        self.running = False
