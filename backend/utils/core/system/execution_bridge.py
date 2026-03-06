import asyncio
import inspect
import threading
from typing import Any, Callable, Coroutine, TypeVar, Union

T = TypeVar("T")

class ExecutionBridge:
    """
    Bridge to simplify calling async code from sync contexts and vice versa.
    Helps during the transition of the codebase to async.
    """

    _loop: asyncio.AbstractEventLoop = None
    _thread: threading.Thread = None

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Get or create a dedicated background event loop for the bridge."""
        if cls._loop is None:
            cls._loop = asyncio.new_event_loop()
            cls._thread = threading.Thread(target=cls._run_loop, args=(cls._loop,), daemon=True)
            cls._thread.start()
        return cls._loop

    @classmethod
    def _run_loop(cls, loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    @classmethod
    def run(cls, func_or_coro: Union[Callable[..., T], Coroutine[Any, Any, T]], *args, **kwargs) -> T:
        """
        Smart execution:
        - If it's a coroutine, runs it in the bridge loop and waits for result.
        - If it's a callable that returns a coroutine, calls it and runs the coroutine.
        - If it's a normal sync function, calls it directly.
        """
        # 1. Handle direct coroutine object
        if inspect.iscoroutine(func_or_coro):
            return cls._run_async(func_or_coro)

        # 2. Handle callable
        if callable(func_or_coro):
            # Check if the function itself is async
            if inspect.iscoroutinefunction(func_or_coro):
                return cls._run_async(func_or_coro(*args, **kwargs))
            
            # Call it normally
            result = func_or_coro(*args, **kwargs)
            
            # If the result happens to be a coroutine (rare but possible)
            if inspect.iscoroutine(result):
                return cls._run_async(result)
            
            return result

        return func_or_coro

    @classmethod
    def _run_async(cls, coro: Coroutine) -> Any:
        """Runs a coroutine in the background loop and blocks for the result."""
        try:
            # If we are already in the same loop (e.g. recursive calls), we can't block
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if current_loop == cls.get_loop():
                # We are ALREADY in the bridge loop. 
                # We can't block with result() without deadlock.
                # However, we must ensure the coroutine is at least scheduled or run.
                # In a bridge scenario, this is usually a bug, but let's try to survive.
                # We'll schedule it and return None, or raise if it's critical.
                # For events, scheduling is enough.
                asyncio.create_task(coro)
                return None

            future = asyncio.run_coroutine_threadsafe(coro, cls.get_loop())
            return future.result()
        except Exception as e:
            # Log error or re-raise
            raise e

# Global convenience instance
bridge = ExecutionBridge
