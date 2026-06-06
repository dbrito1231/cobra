"""In-process event bus C1–C3."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from orchestrator.models import BusEvent, ComponentName

Subscriber = Callable[[BusEvent], None]


class EventBus:
    """Components publish events; orchestrator routes to subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, event: BusEvent) -> None:
        for handler in self._subscribers.get(event.topic, []):
            handler(event)
        for handler in self._subscribers.get("*", []):
            handler(event)

    def route(
        self,
        topic: str,
        source: ComponentName,
        payload: dict | None = None,
    ) -> BusEvent:
        event = BusEvent(topic=topic, source=source, payload=payload or {})
        self.publish(event)
        return event
