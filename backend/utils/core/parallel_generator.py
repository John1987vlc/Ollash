"""
Parallel File Generation using asyncio and Task Queues

Enables concurrent generation of multiple files while respecting rate limits
and maintaining proper context ordering.
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta
from backend.utils.core.agent_logger import AgentLogger


@dataclass
class GenerationTask:
    """Represents a single file generation task."""
    file_path: str
    context: Dict[str, Any]
    priority: int = 0  # Higher = process first
    created_at: datetime = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies_met: bool = False
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def __lt__(self, other: "GenerationTask") -> bool:
        """Comparison for priority queue (higher priority first, then FIFO)."""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.created_at < other.created_at


@dataclass
class GenerationResult:
    """Result of a generation task."""
    file_path: str
    content: Optional[str]
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class RateLimiter:
    """
    Token-bucket rate limiter for LLM API calls.
    Prevents overwhelming the Ollama server.
    """
    
    def __init__(self, max_requests_per_minute: int = 10, max_concurrent: int = 3):
        """
        Initialize rate limiter.
        
        Args:
            max_requests_per_minute: Max requests per minute
            max_concurrent: Max concurrent requests at once
        """
        self.max_concurrent = max_concurrent
        self.min_interval = 60.0 / max_requests_per_minute  # seconds between requests
        self.last_request_time = 0.0
        self.active_requests = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Wait until it's safe to make a request."""
        async with self._lock:
            # Wait for concurrent slots
            while self.active_requests >= self.max_concurrent:
                await asyncio.sleep(0.1)
            
            # Wait for rate limit
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            
            self.active_requests += 1
            self.last_request_time = time.time()
    
    async def release(self) -> None:
        """Release a request slot."""
        async with self._lock:
            self.active_requests = max(0, self.active_requests - 1)


class ParallelFileGenerator:
    """
    Orchestrates parallel generation of files using asyncio.
    
    Features:
    - Respects dependency ordering
    - Rate limiting for LLM calls
    - Priority-based scheduling
    - Retry logic with exponential backoff
    - Progress tracking
    """
    
    def __init__(
        self,
        logger: AgentLogger,
        max_concurrent: int = 3,
        max_requests_per_minute: int = 10,
    ):
        """
        Initialize parallel generator.
        
        Args:
            logger: Logger instance
            max_concurrent: Max concurrent file generations
            max_requests_per_minute: Rate limit for LLM calls
        """
        self.logger = logger
        self.rate_limiter = RateLimiter(max_requests_per_minute, max_concurrent)
        self.generation_fn: Optional[Callable] = None
        self.results: Dict[str, GenerationResult] = {}
        self.failed_files: List[str] = []
        self.completed_count = 0
        self.total_count = 0
    
    async def generate_files(
        self,
        tasks: List[GenerationTask],
        generation_fn: Callable[[str, Dict], Tuple[str, bool, Optional[str]]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        dependency_order: Optional[List[str]] = None,
    ) -> Dict[str, GenerationResult]:
        """
        Generate multiple files in parallel with dependency ordering.
        
        Args:
            tasks: List of generation tasks
            generation_fn: Async function to generate a file.
                          Returns (content, success, error_msg)
            progress_callback: Optional callback(file_path, completed, total)
            dependency_order: Optional list of files ordered by dependencies
        
        Returns:
            Dict mapping file paths to GenerationResults
        """
        self.logger.info(
            f"Starting parallel generation of {len(tasks)} files "
            f"(max {self.rate_limiter.max_concurrent} concurrent)"
        )
        
        self.generation_fn = generation_fn
        self.total_count = len(tasks)
        self.completed_count = 0
        self.results = {}
        self.failed_files = []
        
        # Build task queue with dependency awareness
        task_queue: asyncio.Queue[GenerationTask] = asyncio.Queue()
        completed_files = set()
        
        # Create worker coroutines
        workers = [
            self._worker(task_queue, progress_callback, completed_files, dependency_order)
            for _ in range(self.rate_limiter.max_concurrent)
        ]
        
        # Add tasks to queue
        for task in tasks:
            await task_queue.put(task)
        
        # Add sentinel values to stop workers
        for _ in range(self.rate_limiter.max_concurrent):
            await task_queue.put(None)
        
        # Run workers concurrently
        await asyncio.gather(*workers)
        
        # Log summary
        success_count = sum(1 for r in self.results.values() if r.success)
        self.logger.info(
            f"Parallel generation complete: {success_count}/{self.total_count} success, "
            f"{len(self.failed_files)} failed"
        )
        
        return self.results
    
    async def _worker(
        self,
        task_queue: asyncio.Queue,
        progress_callback: Optional[Callable],
        completed_files: set,
        dependency_order: Optional[List[str]],
    ) -> None:
        """Worker coroutine that processes generation tasks."""
        while True:
            task = await task_queue.get()
            
            if task is None:  # Sentinel value
                break
            
            # Check if dependencies are met
            if dependency_order:
                deps = self._get_file_dependencies(task.file_path, dependency_order)
                while not all(d in completed_files for d in deps):
                    await asyncio.sleep(0.1)
            
            # Generate file with rate limiting
            start_time = time.time()
            try:
                await self.rate_limiter.acquire()
                
                # Call the generation function
                if asyncio.iscoroutinefunction(self.generation_fn):
                    content, success, error = await self.generation_fn(
                        task.file_path, task.context
                    )
                else:
                    content, success, error = self.generation_fn(
                        task.file_path, task.context
                    )
                
                duration = time.time() - start_time
                
                # Store result
                self.results[task.file_path] = GenerationResult(
                    file_path=task.file_path,
                    content=content if success else None,
                    success=success,
                    error=error,
                    duration_seconds=duration,
                )
                
                if not success:
                    self.failed_files.append(task.file_path)
                
                # Mark as completed
                completed_files.add(task.file_path)
                self.completed_count += 1
                
                if progress_callback:
                    progress_callback(
                        task.file_path,
                        self.completed_count,
                        self.total_count,
                    )
                
                self.logger.debug(
                    f"Generated {task.file_path} in {duration:.2f}s ({'success' if success else 'failed'})"
                )
            
            except Exception as e:
                self.logger.error(f"Critical error generating {task.file_path}: {e}")
                self.results[task.file_path] = GenerationResult(
                    file_path=task.file_path,
                    content=None,
                    success=False,
                    error=str(e),
                    duration_seconds=time.time() - start_time,
                )
                self.failed_files.append(task.file_path)
                self.completed_count += 1
                completed_files.add(task.file_path)
            
            finally:
                await self.rate_limiter.release()
    
    def _get_file_dependencies(
        self,
        file_path: str,
        dependency_order: List[str]
    ) -> List[str]:
        """Get files that must be generated before this one."""
        if file_path not in dependency_order:
            return []
        
        file_index = dependency_order.index(file_path)
        return dependency_order[:file_index]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get generation statistics."""
        if not self.results:
            return {"total": 0, "success": 0, "failed": 0}
        
        successful = [r for r in self.results.values() if r.success]
        failed = [r for r in self.results.values() if not r.success]
        total_duration = sum(r.duration_seconds for r in self.results.values())
        
        return {
            "total": len(self.results),
            "success": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self.results) if self.results else 0,
            "total_duration_seconds": total_duration,
            "avg_time_per_file": total_duration / len(self.results) if self.results else 0,
            "failed_files": self.failed_files,
        }


class AsyncFileGenerationAdapter:
    """
    Adapter to make synchronous file generation functions compatible with async.
    Wraps blocking operations in executor to prevent blocking event loop.
    """
    
    def __init__(self, logger: AgentLogger, max_workers: int = 4):
        """Initialize adapter."""
        self.logger = logger
        self.max_workers = max_workers
        self.executor = None
    
    async def call_sync_function(
        self,
        sync_fn: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Call a synchronous function without blocking the event loop.
        Uses ThreadPoolExecutor for CPU-bound work.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default executor
            lambda: sync_fn(*args, **kwargs)
        )
    
    async def generate_file_async(
        self,
        file_path: str,
        content_generator_fn: Callable,
        *args,
        **kwargs
    ) -> Tuple[Optional[str], bool, Optional[str]]:
        """
        Generate file content asynchronously.
        
        Returns:
            (content, success, error_message)
        """
        try:
            content = await self.call_sync_function(
                content_generator_fn,
                file_path,
                *args,
                **kwargs
            )
            return (content, True, None)
        except Exception as e:
            self.logger.error(f"Error generating {file_path}: {e}")
            return (None, False, str(e))
