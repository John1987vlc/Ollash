from typing import Callable, Dict, Any, List

class EventPublisher:
    """A simple publisher-subscriber mechanism for emitting events."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Registers a callback function for a given event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, **kwargs: Any):
        """Publishes an event to all subscribed listeners."""
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event_type=event_type, **kwargs)
                except Exception as e:
                    # Log the error but don't stop other subscribers
                    print(f"Error in event subscriber for '{event_type}': {e}")
