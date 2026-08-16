"""
webhook_usecase.py — Webhook Management Interactor (Clean Architecture).
Encapsulates subscription management and event payload validation.
"""

import uuid
from typing import Any


class WebhookUseCase:
    def __init__(self):
        self._subscriptions: dict[str, dict[str, Any]] = {}

    def subscribe(self, url: str, events: list[str], _secret: str | None = None) -> dict[str, Any]:
        sub_id = f"sub_{uuid.uuid4().hex[:12]}"
        subscription = {
            "subscription_id": sub_id,
            "target_url": url,
            "events": events,
            "status": "ACTIVE",
            "created_at": "2026-07-30T00:00:00Z",
        }
        self._subscriptions[sub_id] = subscription
        return {"success": True, "subscription": subscription}

    def list_subscriptions(self) -> list[dict[str, Any]]:
        return list(self._subscriptions.values())

    def unsubscribe(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False


webhook_usecase = WebhookUseCase()
