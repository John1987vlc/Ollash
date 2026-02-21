"""
Load Simulator and Application Benchmarker

Runs stress tests on generated applications and produces
performance reports.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.command_executor import CommandExecutor


@dataclass
class LoadTestResult:
    """Result of a load test run."""

    target: str
    concurrent_users: int
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    requests_per_second: float
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "concurrent_users": self.concurrent_users,
            "duration_seconds": self.duration_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round(self.success_rate * 100, 2),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "min_response_time_ms": round(self.min_response_time_ms, 2),
            "max_response_time_ms": round(self.max_response_time_ms, 2),
            "p95_response_time_ms": round(self.p95_response_time_ms, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "errors": self.errors[:10],
        }


@dataclass
class ScriptBenchResult:
    """Result of benchmarking a script."""

    script_path: str
    iterations: int
    total_time_seconds: float
    avg_time_seconds: float
    min_time_seconds: float
    max_time_seconds: float
    exit_codes: List[int] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "script_path": self.script_path,
            "iterations": self.iterations,
            "total_time_seconds": round(self.total_time_seconds, 3),
            "avg_time_seconds": round(self.avg_time_seconds, 3),
            "min_time_seconds": round(self.min_time_seconds, 3),
            "max_time_seconds": round(self.max_time_seconds, 3),
            "success_rate": round(self.exit_codes.count(0) / max(1, len(self.exit_codes)) * 100, 1),
            "errors": self.errors[:10],
        }


class LoadSimulator:
    """Runs load tests and benchmarks on generated applications.

    Supports:
    - HTTP endpoint load testing (using curl/ab if available)
    - Script execution benchmarking
    - Performance report generation
    """

    def __init__(self, command_executor: CommandExecutor, logger: AgentLogger):
        self.command_executor = command_executor
        self.logger = logger

    async def run_http_benchmark(
        self,
        target_url: str,
        concurrent: int = 10,
        total_requests: int = 100,
        timeout: int = 30,
    ) -> LoadTestResult:
        """Run an HTTP load test against a target URL.

        Uses Apache Bench (ab) or curl with concurrent connections.
        Falls back to simple sequential requests if no tools available.
        """
        self.logger.info(f"Starting HTTP benchmark: {target_url} ({concurrent} concurrent, {total_requests} requests)")

        # Try Apache Bench first
        try:
            result = await self._run_ab(target_url, concurrent, total_requests, timeout)
            if result:
                return result
        except Exception as e:
            self.logger.debug(f"ab not available: {e}")

        # Fallback: simple sequential benchmark
        return await self._run_simple_benchmark(target_url, total_requests, timeout)

    async def _run_ab(self, url: str, concurrent: int, total: int, timeout: int) -> Optional[LoadTestResult]:
        """Run Apache Bench."""
        import re

        cmd = f"ab -n {total} -c {concurrent} -t {timeout} {url}/"
        result = self.command_executor.execute(cmd, timeout=timeout + 10)

        if result.get("returncode") != 0:
            return None

        output = result.get("stdout", "")

        # Parse ab output
        rps = (
            float(re.search(r"Requests per second:\s+([\d.]+)", output).group(1))
            if re.search(r"Requests per second", output)
            else 0
        )
        avg_time = (
            float(re.search(r"Time per request:\s+([\d.]+)\s+\[ms\].*mean\)", output).group(1))
            if re.search(r"Time per request.*mean\)", output)
            else 0
        )
        failed = (
            int(re.search(r"Failed requests:\s+(\d+)", output).group(1)) if re.search(r"Failed requests", output) else 0
        )

        return LoadTestResult(
            target=url,
            concurrent_users=concurrent,
            duration_seconds=timeout,
            total_requests=total,
            successful_requests=total - failed,
            failed_requests=failed,
            avg_response_time_ms=avg_time,
            min_response_time_ms=0,
            max_response_time_ms=0,
            p95_response_time_ms=0,
            requests_per_second=rps,
        )

    async def _run_simple_benchmark(self, url: str, total: int, timeout: int) -> LoadTestResult:
        """Simple sequential HTTP benchmark using curl."""
        times = []
        errors = []
        start = time.time()

        for i in range(min(total, 50)):  # Limit for sequential
            try:
                cmd = f'curl -s -o /dev/null -w "%{{time_total}}" -m {timeout} {url}'
                result = self.command_executor.execute(cmd, timeout=timeout + 5)
                if result.get("returncode") == 0:
                    t = float(result.get("stdout", "0").strip().strip('"'))
                    times.append(t * 1000)  # Convert to ms
                else:
                    errors.append(f"Request {i}: exit code {result.get('returncode')}")
            except Exception as e:
                errors.append(str(e))

        elapsed = time.time() - start
        times.sort()

        return LoadTestResult(
            target=url,
            concurrent_users=1,
            duration_seconds=elapsed,
            total_requests=len(times) + len(errors),
            successful_requests=len(times),
            failed_requests=len(errors),
            avg_response_time_ms=sum(times) / max(1, len(times)),
            min_response_time_ms=times[0] if times else 0,
            max_response_time_ms=times[-1] if times else 0,
            p95_response_time_ms=times[int(len(times) * 0.95)] if times else 0,
            requests_per_second=len(times) / max(0.001, elapsed),
            errors=errors,
        )

    async def run_script_benchmark(
        self, script_path: str, iterations: int = 10, timeout: int = 60
    ) -> ScriptBenchResult:
        """Benchmark a script by running it multiple times."""
        self.logger.info(f"Benchmarking script: {script_path} ({iterations} iterations)")

        times = []
        exit_codes = []
        errors = []

        for i in range(iterations):
            start = time.time()
            try:
                result = self.command_executor.execute(f"python {script_path}", timeout=timeout)
                elapsed = time.time() - start
                times.append(elapsed)
                exit_codes.append(result.get("returncode", -1))
                if result.get("returncode") != 0:
                    stderr = result.get("stderr", "")
                    if stderr:
                        errors.append(f"Iteration {i}: {stderr[:200]}")
            except Exception as e:
                elapsed = time.time() - start
                times.append(elapsed)
                exit_codes.append(-1)
                errors.append(f"Iteration {i}: {str(e)[:200]}")

        return ScriptBenchResult(
            script_path=script_path,
            iterations=iterations,
            total_time_seconds=sum(times),
            avg_time_seconds=sum(times) / max(1, len(times)),
            min_time_seconds=min(times) if times else 0,
            max_time_seconds=max(times) if times else 0,
            exit_codes=exit_codes,
            errors=errors,
        )

    def generate_report(self, results: List[Any]) -> str:
        """Generate a markdown performance report."""
        lines = ["# Performance Report\n"]

        for r in results:
            if isinstance(r, LoadTestResult):
                lines.extend(
                    [
                        f"## HTTP Load Test: {r.target}\n",
                        f"- Concurrent users: {r.concurrent_users}",
                        f"- Total requests: {r.total_requests}",
                        f"- Success rate: {r.success_rate * 100:.1f}%",
                        f"- Avg response time: {r.avg_response_time_ms:.1f}ms",
                        f"- Requests/second: {r.requests_per_second:.1f}",
                        "",
                    ]
                )
            elif isinstance(r, ScriptBenchResult):
                lines.extend(
                    [
                        f"## Script Benchmark: {r.script_path}\n",
                        f"- Iterations: {r.iterations}",
                        f"- Avg time: {r.avg_time_seconds:.3f}s",
                        f"- Min/Max: {r.min_time_seconds:.3f}s / {r.max_time_seconds:.3f}s",
                        f"- Success rate: {r.exit_codes.count(0) / max(1, len(r.exit_codes)) * 100:.0f}%",
                        "",
                    ]
                )

        return "\n".join(lines)
