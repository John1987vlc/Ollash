import threading
import time


class Heartbeat:
    """Background thread that prints elapsed time periodically while waiting for a slow model response."""

    def __init__(self, model_name, task_label, interval=30, logger=None):
        self.model_name = model_name
        self.task_label = task_label
        self.interval = interval
        self.logger = logger
        self._stop = threading.Event()
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            elapsed = int(time.time() - self._start_time)
            mins, secs = divmod(elapsed, 60)
            msg = f"{self.model_name} | {self.task_label} — {mins}m {secs}s elapsed..."
            if self.logger:
                self.logger.info(msg)
            else:
                print(f"    ⏳ {msg}", flush=True)

    def start(self):
        self._start_time = time.time()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
