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

    def publish(self, event_type: str, event_data: Dict[str, Any] = None, **kwargs: Any):
        """Publishes an event to all subscribed listeners."""
        if event_type not in self._subscribers:
            return # No subscribers for this event type

        full_event_data = event_data if event_data is not None else {}
        full_event_data.update(kwargs) # Merge additional kwargs into event_data

        for callback in self._subscribers[event_type]:
            try:
                # Pass event_type and the combined event_data to the callback
                callback(event_type=event_type, event_data=full_event_data)
            except Exception as e:
                # Log the error but don't stop other subscribers
                print(f"Error in event subscriber for '{event_type}': {e}")
