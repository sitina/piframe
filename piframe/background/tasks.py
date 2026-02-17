"""
Background task management for PiFrame application.
Coordinates weather refresh, image preloading, and cache cleanup.
"""

import time
import threading
from typing import Optional, List, Callable
from dataclasses import dataclass

from ..config.settings import Config
from ..utils.logging import LoggerMixin, get_logger


@dataclass
class TaskInfo:
    """Information about a background task."""
    name: str
    function: Callable
    interval: float
    error_interval: float
    thread: Optional[threading.Thread] = None
    running: bool = False
    last_run: float = 0
    error_count: int = 0


class BackgroundTaskManager(LoggerMixin):
    """Manager for coordinating background tasks."""
    
    def __init__(self, config: Config, enabled: bool = True):
        """
        Initialize background task manager.
        
        Args:
            config: Application configuration
            enabled: Whether background tasks should be enabled
        """
        self.config = config
        self.enabled = enabled
        self.tasks: List[TaskInfo] = []
        self._shutdown_event = threading.Event()
        
        self.logger.info(f"Background task manager initialized (enabled: {enabled})")
    
    def add_task(self, name: str, function: Callable, 
                interval: Optional[float] = None,
                error_interval: Optional[float] = None) -> None:
        """
        Add a background task.
        
        Args:
            name: Task name for logging
            function: Function to execute
            interval: Normal execution interval in seconds
            error_interval: Retry interval after error in seconds
        """
        if interval is None:
            interval = self.config.background_refresh_interval
        if error_interval is None:
            error_interval = self.config.error_retry_interval
        
        task = TaskInfo(
            name=name,
            function=function,
            interval=interval,
            error_interval=error_interval
        )
        
        self.tasks.append(task)
        self.logger.info(f"Added background task: {name} (interval: {interval}s)")
    
    def start_all(self) -> None:
        """Start all registered background tasks."""
        if not self.enabled:
            self.logger.info("Background tasks disabled, not starting")
            return
        
        self.logger.info(f"Starting {len(self.tasks)} background tasks")
        
        for task in self.tasks:
            if not task.running:
                self._start_task(task)
        
        self.logger.info("All background tasks started")
    
    def stop_all(self) -> None:
        """Stop all background tasks."""
        self.logger.info("Stopping all background tasks")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for threads to finish
        for task in self.tasks:
            if task.thread and task.thread.is_alive():
                self.logger.debug(f"Waiting for task {task.name} to finish")
                task.thread.join(timeout=5.0)
                
                if task.thread.is_alive():
                    self.logger.warning(f"Task {task.name} did not stop gracefully")
                else:
                    self.logger.debug(f"Task {task.name} stopped")
            
            task.running = False
            task.thread = None
        
        self.logger.info("All background tasks stopped")
    
    def restart_task(self, name: str) -> bool:
        """
        Restart a specific task.
        
        Args:
            name: Name of task to restart
            
        Returns:
            True if task was found and restarted
        """
        for task in self.tasks:
            if task.name == name:
                self.logger.info(f"Restarting task: {name}")
                
                # Stop the task
                if task.thread and task.thread.is_alive():
                    task.running = False
                    task.thread.join(timeout=2.0)
                
                # Reset error count and restart
                task.error_count = 0
                self._start_task(task)
                return True
        
        self.logger.warning(f"Task not found for restart: {name}")
        return False
    
    def get_task_status(self) -> List[dict]:
        """
        Get status information for all tasks.
        
        Returns:
            List of task status dictionaries
        """
        status_list = []
        current_time = time.time()
        
        for task in self.tasks:
            status = {
                'name': task.name,
                'running': task.running,
                'interval': task.interval,
                'error_interval': task.error_interval,
                'error_count': task.error_count,
                'last_run_ago': current_time - task.last_run if task.last_run > 0 else None,
                'thread_alive': task.thread.is_alive() if task.thread else False
            }
            status_list.append(status)
        
        return status_list
    
    def _start_task(self, task: TaskInfo) -> None:
        """Start a single background task."""
        task.running = True
        task.thread = threading.Thread(
            target=self._task_runner,
            args=(task,),
            daemon=True,
            name=f"BG-{task.name}"
        )
        task.thread.start()
        
        self.logger.debug(f"Started background task: {task.name}")
    
    def _task_runner(self, task: TaskInfo) -> None:
        """
        Main runner for a background task.
        
        Args:
            task: Task information
        """
        self.logger.debug(f"Background task runner started: {task.name}")
        
        while task.running and not self._shutdown_event.is_set():
            try:
                # Execute the task function
                self.logger.debug(f"Executing task: {task.name}")
                start_time = time.time()
                
                task.function()
                
                execution_time = time.time() - start_time
                task.last_run = time.time()
                task.error_count = 0  # Reset error count on success
                
                self.logger.debug(f"Task {task.name} completed in {execution_time:.2f}s")
                
                # Wait for next execution
                self._sleep_interruptible(task.interval)
                
            except Exception as e:
                task.error_count += 1
                self.logger.error(f"Error in background task {task.name}: {e}", exc_info=True)
                
                # Use error retry interval
                retry_delay = min(task.error_interval * (2 ** min(task.error_count - 1, 5)), 300)
                self.logger.info(f"Task {task.name} will retry in {retry_delay:.1f}s (error #{task.error_count})")
                
                self._sleep_interruptible(retry_delay)
        
        self.logger.debug(f"Background task runner finished: {task.name}")
    
    def _sleep_interruptible(self, duration: float) -> None:
        """
        Sleep for duration but wake up if shutdown is signaled.
        
        Args:
            duration: Sleep duration in seconds
        """
        self._shutdown_event.wait(timeout=duration)
    
    def is_enabled(self) -> bool:
        """Check if background tasks are enabled."""
        return self.enabled
    
    def enable(self) -> None:
        """Enable background tasks and start them if not already running."""
        if not self.enabled:
            self.enabled = True
            self.logger.info("Background tasks enabled")
            self.start_all()
    
    def disable(self) -> None:
        """Disable background tasks and stop them."""
        if self.enabled:
            self.enabled = False
            self.logger.info("Background tasks disabled")
            self.stop_all()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure tasks are stopped."""
        self.stop_all()


class ImagePreloader:
    """
    Callable that refreshes the Drive file list and preloads random images
    into the download cache so they're ready to serve instantly.

    Periodically clears the download cache to ensure image variety.
    """

    # Clear the download cache every N calls to rotate cached images
    CACHE_CLEAR_EVERY_N_CALLS = 5
    # Number of random images to preload per invocation
    IMAGES_TO_PRELOAD = 2

    def __init__(self, drive_service):
        self.drive_service = drive_service
        self.call_count = 0
        self._logger = get_logger(__name__)

    def __call__(self):
        self.drive_service.force_refresh_file_list()

        self.call_count += 1
        if self.call_count % self.CACHE_CLEAR_EVERY_N_CALLS == 0:
            self.drive_service.clear_download_cache()

        for i in range(self.IMAGES_TO_PRELOAD):
            try:
                image_info = self.drive_service.get_random_image(avoid_recent=False)
                if image_info:
                    self.drive_service.download_file(image_info['id'])
            except Exception as e:
                self._logger.warning(f"Failed to preload image {i+1}/{self.IMAGES_TO_PRELOAD}: {e}")


# Cache cleanup interval constants (seconds)
CACHE_CLEANUP_INTERVAL = 1800   # 30 minutes
CACHE_CLEANUP_ERROR_INTERVAL = 300  # 5 minutes


def create_standard_tasks(weather_service, drive_service, image_service, config) -> BackgroundTaskManager:
    """
    Create a task manager with standard PiFrame background tasks.

    Args:
        weather_service: Weather service instance
        drive_service: Drive service instance
        image_service: Image service instance
        config: Application configuration

    Returns:
        Configured BackgroundTaskManager
    """
    task_manager = BackgroundTaskManager(config)

    def refresh_weather():
        weather_service.get_current_weather(force_refresh=True)
        weather_service.get_forecast(force_refresh=True)

    task_manager.add_task(
        name="weather_refresh",
        function=refresh_weather,
        interval=config.background_refresh_interval,
        error_interval=config.error_retry_interval
    )

    task_manager.add_task(
        name="image_preload",
        function=ImagePreloader(drive_service),
        interval=config.preload_interval,
        error_interval=config.preload_error_retry_interval
    )

    task_manager.add_task(
        name="cache_cleanup",
        function=weather_service.cleanup_expired_cache,
        interval=CACHE_CLEANUP_INTERVAL,
        error_interval=CACHE_CLEANUP_ERROR_INTERVAL,
    )

    return task_manager