import asyncio
import inspect
from typing import Any, Callable, Dict, List
from backend.utils.core.system.execution_bridge import bridge


class EventPublisher:
    """A publisher-subscriber mechanism for emitting events, supporting both sync and async callbacks."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        """Registers a callback function for a given event type.
        If the callback is already subscribed to this event type, it won't be added again.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """Unregisters a callback function from a given event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass  # Callback not found, already unsubscribed or never subscribed

    def has_subscribers(self, event_type: str) -> bool:
        """Check if there are any active subscribers for a given event type."""
        return event_type in self._subscribers and len(self._subscribers[event_type]) > 0

    async def publish(self, event_type: str, event_data: Dict[str, Any] = None, **kwargs: Any):
        """Publishes an event to all subscribed listeners asynchronously."""
        if event_type not in self._subscribers:
            return  # No subscribers for this event type

        full_event_data = event_data if event_data is not None else {}
        full_event_data.update(kwargs)  # Merge additional kwargs into event_data

        tasks = []
        for callback in self._subscribers[event_type]:
            try:
                # F31: Enhanced coroutine detection
                # Some callbacks might be sync wrappers that return a coroutine
                result = callback(event_type=event_type, event_data=full_event_data)
                if inspect.isawaitable(result):
                    tasks.append(result)
            except Exception as e:
                # Log the error but don't stop other subscribers
                print(f"Error in event subscriber for '{event_type}': {e}")

        if tasks:
            # Filter out None results if any sync callback returned nothing
            tasks = [t for t in tasks if t is not None]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def publish_sync(self, event_type: str, event_data: Dict[str, Any] = None, **kwargs: Any):
        """Synchronous version of publish, useful for threads or mixed contexts."""
        # Use the bridge's background loop directly to schedule the task
        # This is the safest way to ensure the coroutine is awaited without blocking the current thread if it's already in a loop.
        try:
            loop = bridge.get_loop()
            if loop.is_running():
                # We use run_coroutine_threadsafe to schedule it on the bridge loop
                asyncio.run_coroutine_threadsafe(self.publish(event_type, event_data, **kwargs), loop)
                return
        except Exception:
            pass

        # Fallback to bridge.run if something goes wrong or loop is not running
        return bridge.run(self.publish, event_type, event_data, **kwargs)
