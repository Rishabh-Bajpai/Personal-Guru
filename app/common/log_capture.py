import sys
import threading
import time
import queue
import atexit
import datetime
import logging

class LogCapture:
    """
    Captures stdout and stderr, buffers them, and asynchronously writes to the database.
    Uses a queue to ensure non-blocking application performance.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, app=None):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(LogCapture, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, app=None):
        if self._initialized:
            return
            
        self.app = app
        self.queue = queue.Queue()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stop_event = threading.Event()
        self.worker_thread = None
        
        # Configuration
        self.batch_size = 100
        self.flush_interval = 5  # seconds
        
        # Install hooks
        sys.stdout = self._make_stream_wrapper(self.original_stdout, 'stdout')
        sys.stderr = self._make_stream_wrapper(self.original_stderr, 'stderr')
        
        # Start background worker
        self._start_worker()
        
        # cleanup on exit
        atexit.register(self.stop)
        
        self._initialized = True

    def _make_stream_wrapper(self, original_stream, stream_name):
        """Creates a wrapper that writes to both original stream and queue."""
        capture_instance = self
        
        class StreamWrapper:
            def write(self, message):
                # Write to original stream (console)
                original_stream.write(message)
                
                # Filter out empty writes or just newlines if desired, 
                # but often we want to capture everything.
                if message:
                    capture_instance.queue.put({
                        'stream': stream_name,
                        'message': message,
                        'timestamp': datetime.datetime.utcnow().isoformat()
                    })

            def flush(self):
                original_stream.flush()
                
            def isatty(self):
                return getattr(original_stream, 'isatty', lambda: False)()
                
        return StreamWrapper()

    def _start_worker(self):
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(
                target=self._worker_loop, 
                name="LogCaptureWorker",
                daemon=True
            )
            self.worker_thread.start()

    def _worker_loop(self):
        """Background loop to flush logs."""
        buffer = []
        last_flush = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Wait for item with timeout (flush interval)
                remaining = self.flush_interval - (time.time() - last_flush)
                if remaining <= 0:
                    # Avoid timeout=0 which can cause a tight loop; use a small minimum delay
                    remaining = 0.1
                
                item = self.queue.get(timeout=remaining)
                buffer.append(item)
                
                # Flush if full
                if len(buffer) >= self.batch_size:
                    self._flush(buffer)
                    buffer = []
                    last_flush = time.time()
                    
            except queue.Empty:
                # Timeout reached, flush if we have anything
                if buffer:
                    self._flush(buffer)
                    buffer = []
                    last_flush = time.time()
                continue
                
        # Final flush on stop
        if buffer:
            self._flush(buffer)
            
        # Drain queue
        rest = []
        while not self.queue.empty():
            try:
                rest.append(self.queue.get_nowait())
            except queue.Empty:
                break
        if rest:
            self._flush(rest)

    def _flush(self, logs):
        """Writes buffered logs to database."""
        if not self.app:
            return

        try:
            with self.app.app_context():
                # Avoid circular imports
                from app.core.models import TelemetryLog, Installation
                from app.core.extensions import db

                # We need an installation ID. Since this is background, we can't reliably get current_user.
                # We'll use the first installation found or a system sentinel.
                # In a single-user app context, this is usually acceptable.
                inst = Installation.query.first()
                if not inst:
                    return

                # Create one telemetry entry for the batch
                log_entry = TelemetryLog(
                    installation_id=inst.installation_id,
                    session_id='system_background',
                    event_type='terminal_log',
                    triggers={'source': 'system_capture'},
                    payload={'logs': logs}
                )
                
                db.session.add(log_entry)
                db.session.commit()
                
        except Exception as e:
            # Suppress "no such table" errors which happen during startup/setup
            # This avoids noise when logging happens before DB initialization
            if "no such table" in str(e):
                return

            # Fallback to original stderr if DB fails
            self.original_stderr.write(f"LogCapture Flush Failed: {e}\n")

    def stop(self):
        """Stops the worker thread and restores streams."""
        self.stop_event.set()
        
        # Restore streams
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
            if self.worker_thread.is_alive():
                logging.getLogger(__name__).warning(
                    "LogCapture worker thread did not terminate within the 2.0 second timeout; "
                    "some buffered logs may not have been flushed."
                )
