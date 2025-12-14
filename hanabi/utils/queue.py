import docker
import sys
import json
from datetime import datetime
from queue import Queue
from threading import Thread, Event


class DockerLogQueue:
    """
    A queue class that streams Docker container logs as JSON objects.
    Uses a background thread to continuously read logs and put them into a queue.
    """
    
    def __init__(self, container_name="falco", max_queue_size=10000):
        """
        Initialize the Docker log queue.
        
        Args:
            container_name: Name or ID of the Docker container
            max_queue_size: Maximum number of items in the queue (default: 10000)
        """
        self.container_name = container_name
        self.queue = Queue(maxsize=max_queue_size)
        self.stop_event = Event()
        self.thread = None
        self.client = None
        self.container = None
        self.line_count = 0
        self.error_count = 0
        
    def start(self):
        """Start streaming logs in a background thread."""
        try:
            self.client = docker.from_env()
            self.container = self.client.containers.get(self.container_name)
            print(f"✅ Connected to container '{self.container_name}' (ID: {self.container.short_id})", file=sys.stderr)
        except docker.errors.DockerException as e:
            raise Exception(f"Failed to connect to Docker daemon: {e}")
        except docker.errors.NotFound:
            raise Exception(f"Container '{self.container_name}' not found")
        
        # Start background thread
        self.thread = Thread(target=self._stream_logs, daemon=True)
        self.thread.start()
        print(f"✅ Log streaming started", file=sys.stderr)
        
    def _stream_logs(self):
        """Internal method to stream logs (runs in background thread)."""
        log_stream = self.container.logs(stream=True, follow=True, stdout=True, stderr=True, since=int(datetime.now().timestamp()))
        buffer = ""
        
        try:
            for chunk in log_stream:
                if self.stop_event.is_set():
                    break
                
                try:
                    buffer += chunk.decode('utf-8')
                except (KeyboardInterrupt, SystemExit):
                    break
                
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    
                    if line.strip():
                        self.line_count += 1
                        
                        try:
                            json_obj = json.loads(line)
                            # Put JSON object into queue (blocks if queue is full)
                            self.queue.put(json_obj)
                        except json.JSONDecodeError as e:
                            self.error_count += 1
                            print(f"Invalid JSON on line {self.line_count}: {e}", file=sys.stderr)
        except Exception as e:
            if not self.stop_event.is_set():
                print(f"❌ Error in log streaming: {e}", file=sys.stderr)
    
    def get(self, timeout=None):
        """
        Get the next JSON object from the queue.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait indefinitely)
            
        Returns:
            JSON object (dict) or None if timeout occurs
        """
        try:
            return self.queue.get(timeout=timeout)
        except:
            return None
    
    def get_nowait(self):
        """
        Get the next JSON object without blocking.
        
        Returns:
            JSON object (dict) or None if queue is empty
        """
        try:
            return self.queue.get_nowait()
        except:
            return None
    
    def size(self):
        """Get current queue size."""
        return self.queue.qsize()
    
    def is_empty(self):
        """Check if queue is empty."""
        return self.queue.empty()
    
    def get_stats(self):
        """Get statistics about the log stream."""
        return {
            "lines_processed": self.line_count,
            "json_errors": self.error_count,
            "queue_size": self.queue.qsize()
        }
    
    def stop(self):
        """Stop streaming logs and clean up."""
        print(f"\n🛑 Stopping log stream...", file=sys.stderr)
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=2)
        
        stats = self.get_stats()
        print(f"📊 Stats: {stats['lines_processed']} lines, {stats['json_errors']} errors", file=sys.stderr)
