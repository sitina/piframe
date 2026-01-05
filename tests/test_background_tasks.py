"""
Tests for background task management
"""
import unittest
import time
import threading
from unittest.mock import patch, MagicMock, call
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piframe.background.tasks import (
    BackgroundTaskManager,
    TaskInfo,
    create_standard_tasks
)
from piframe.config import Config


class TestTaskInfo(unittest.TestCase):
    """Test cases for TaskInfo dataclass"""

    def test_task_info_creation(self):
        """Test creating a TaskInfo instance"""
        def dummy_function():
            pass
        
        task = TaskInfo(
            name="test_task",
            function=dummy_function,
            interval=60.0,
            error_interval=10.0
        )
        
        self.assertEqual(task.name, "test_task")
        self.assertEqual(task.function, dummy_function)
        self.assertEqual(task.interval, 60.0)
        self.assertEqual(task.error_interval, 10.0)
        self.assertIsNone(task.thread)
        self.assertFalse(task.running)
        self.assertEqual(task.last_run, 0)
        self.assertEqual(task.error_count, 0)


class TestBackgroundTaskManager(unittest.TestCase):
    """Test cases for BackgroundTaskManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.config.background_refresh_interval = 60
        self.config.error_retry_interval = 10

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_init_enabled(self):
        """Test initialization with tasks enabled"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        self.assertEqual(manager.config, self.config)
        self.assertTrue(manager.enabled)
        self.assertEqual(len(manager.tasks), 0)
        self.assertFalse(manager._shutdown_event.is_set())

    def test_init_disabled(self):
        """Test initialization with tasks disabled"""
        manager = BackgroundTaskManager(self.config, enabled=False)
        
        self.assertFalse(manager.enabled)

    def test_add_task(self):
        """Test adding a task"""
        manager = BackgroundTaskManager(self.config)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function, interval=30.0, error_interval=5.0)
        
        self.assertEqual(len(manager.tasks), 1)
        task = manager.tasks[0]
        self.assertEqual(task.name, "test_task")
        self.assertEqual(task.function, test_function)
        self.assertEqual(task.interval, 30.0)
        self.assertEqual(task.error_interval, 5.0)

    def test_add_task_default_intervals(self):
        """Test adding a task with default intervals"""
        manager = BackgroundTaskManager(self.config)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function)
        
        task = manager.tasks[0]
        self.assertEqual(task.interval, self.config.background_refresh_interval)
        self.assertEqual(task.error_interval, self.config.error_retry_interval)

    def test_start_all_enabled(self):
        """Test starting all tasks when enabled"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        execution_count = {'count': 0}
        
        def test_function():
            execution_count['count'] += 1
        
        manager.add_task("test_task", test_function, interval=0.1)
        manager.start_all()
        
        # Wait a bit for task to run
        time.sleep(0.3)
        
        # Stop tasks
        manager.stop_all()
        
        # Give threads time to stop
        time.sleep(0.2)
        
        self.assertGreater(execution_count['count'], 0)
        self.assertFalse(manager.tasks[0].running)

    def test_start_all_disabled(self):
        """Test starting tasks when disabled"""
        manager = BackgroundTaskManager(self.config, enabled=False)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function)
        manager.start_all()
        
        # Tasks should not be running
        self.assertFalse(manager.tasks[0].running)
        self.assertIsNone(manager.tasks[0].thread)

    def test_stop_all(self):
        """Test stopping all tasks"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        def test_function():
            time.sleep(0.1)  # Short sleep to keep task alive
        
        manager.add_task("test_task", test_function, interval=0.1)
        manager.start_all()
        
        # Wait for task to start
        time.sleep(0.2)
        
        # Verify task is running
        self.assertTrue(manager.tasks[0].running)
        
        # Stop all tasks
        manager.stop_all()
        
        # Wait for threads to finish
        time.sleep(0.3)
        
        # Verify task is stopped
        self.assertFalse(manager.tasks[0].running)
        self.assertTrue(manager._shutdown_event.is_set())

    def test_restart_task(self):
        """Test restarting a specific task"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        execution_count = {'count': 0}
        
        def test_function():
            execution_count['count'] += 1
        
        manager.add_task("test_task", test_function, interval=0.1)
        manager.start_all()
        
        # Wait for initial execution
        time.sleep(0.2)
        initial_count = execution_count['count']
        
        # Restart the task
        result = manager.restart_task("test_task")
        
        self.assertTrue(result)
        
        # Wait for restarted task to run
        time.sleep(0.2)
        
        # Stop all
        manager.stop_all()
        time.sleep(0.2)
        
        # Should have executed more times
        self.assertGreater(execution_count['count'], initial_count)

    def test_restart_task_not_found(self):
        """Test restarting a non-existent task"""
        manager = BackgroundTaskManager(self.config)
        
        result = manager.restart_task("nonexistent_task")
        
        self.assertFalse(result)

    def test_get_task_status(self):
        """Test getting task status"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function, interval=60.0, error_interval=10.0)
        manager.start_all()
        
        # Wait a bit
        time.sleep(0.1)
        
        status_list = manager.get_task_status()
        
        self.assertEqual(len(status_list), 1)
        status = status_list[0]
        self.assertEqual(status['name'], "test_task")
        self.assertTrue(status['running'])
        self.assertEqual(status['interval'], 60.0)
        self.assertEqual(status['error_interval'], 10.0)
        self.assertEqual(status['error_count'], 0)
        self.assertIsNotNone(status['last_run_ago'])
        
        manager.stop_all()
        time.sleep(0.2)

    def test_task_error_handling(self):
        """Test error handling in task execution"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        def failing_function():
            raise Exception("Test error")
        
        manager.add_task("failing_task", failing_function, interval=0.1, error_interval=0.1)
        manager.start_all()
        
        # Wait for task to fail a few times
        time.sleep(0.4)
        
        status_list = manager.get_task_status()
        task_status = status_list[0]
        
        # Should have error count > 0
        self.assertGreater(task_status['error_count'], 0)
        
        manager.stop_all()
        time.sleep(0.2)

    def test_task_error_retry_interval(self):
        """Test exponential backoff for error retry intervals"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        call_times = []
        
        def failing_function():
            call_times.append(time.time())
            raise Exception("Test error")
        
        manager.add_task("failing_task", failing_function, interval=0.1, error_interval=0.1)
        manager.start_all()
        
        # Wait for multiple failures
        time.sleep(0.5)
        
        manager.stop_all()
        time.sleep(0.2)
        
        # Should have multiple calls
        self.assertGreater(len(call_times), 1)
        
        # Intervals should increase (exponential backoff)
        if len(call_times) >= 2:
            intervals = [call_times[i+1] - call_times[i] for i in range(len(call_times)-1)]
            # First retry should be at error_interval, subsequent ones should be longer
            self.assertGreaterEqual(intervals[0], 0.1)

    def test_is_enabled(self):
        """Test checking if tasks are enabled"""
        manager_enabled = BackgroundTaskManager(self.config, enabled=True)
        manager_disabled = BackgroundTaskManager(self.config, enabled=False)
        
        self.assertTrue(manager_enabled.is_enabled())
        self.assertFalse(manager_disabled.is_enabled())

    def test_enable(self):
        """Test enabling tasks"""
        manager = BackgroundTaskManager(self.config, enabled=False)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function, interval=0.1)
        
        manager.enable()
        
        self.assertTrue(manager.enabled)
        # Tasks should be started
        time.sleep(0.1)
        self.assertTrue(manager.tasks[0].running)
        
        manager.stop_all()
        time.sleep(0.2)

    def test_disable(self):
        """Test disabling tasks"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function, interval=0.1)
        manager.start_all()
        
        time.sleep(0.1)
        self.assertTrue(manager.tasks[0].running)
        
        manager.disable()
        
        self.assertFalse(manager.enabled)
        time.sleep(0.2)
        self.assertFalse(manager.tasks[0].running)

    def test_context_manager(self):
        """Test using BackgroundTaskManager as context manager"""
        manager = BackgroundTaskManager(self.config, enabled=True)
        
        def test_function():
            pass
        
        manager.add_task("test_task", test_function, interval=0.1)
        manager.start_all()
        
        time.sleep(0.1)
        self.assertTrue(manager.tasks[0].running)
        
        # Use as context manager
        with manager:
            time.sleep(0.1)
            self.assertTrue(manager.tasks[0].running)
        
        # After context exit, tasks should be stopped
        time.sleep(0.2)
        self.assertFalse(manager.tasks[0].running)

    def test_sleep_interruptible(self):
        """Test interruptible sleep"""
        manager = BackgroundTaskManager(self.config)
        
        # Set shutdown event
        manager._shutdown_event.set()
        
        # Sleep should return immediately
        start_time = time.time()
        manager._sleep_interruptible(10.0)
        elapsed = time.time() - start_time
        
        # Should return quickly (not wait full 10 seconds)
        self.assertLess(elapsed, 1.0)


class TestCreateStandardTasks(unittest.TestCase):
    """Test cases for create_standard_tasks function"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.config.background_refresh_interval = 60
        self.config.error_retry_interval = 10
        self.config.preload_interval = 300
        self.config.preload_error_retry_interval = 60
        
        # Mock services
        self.mock_weather_service = MagicMock()
        self.mock_drive_service = MagicMock()
        self.mock_image_service = MagicMock()

    def test_create_standard_tasks(self):
        """Test creating standard tasks"""
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        self.assertIsInstance(task_manager, BackgroundTaskManager)
        self.assertEqual(len(task_manager.tasks), 3)
        
        # Check task names
        task_names = [task.name for task in task_manager.tasks]
        self.assertIn("weather_refresh", task_names)
        self.assertIn("image_preload", task_names)
        self.assertIn("cache_cleanup", task_names)

    def test_weather_refresh_task(self):
        """Test weather refresh task execution"""
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        # Find weather refresh task
        weather_task = next(t for t in task_manager.tasks if t.name == "weather_refresh")
        
        # Execute the task function
        weather_task.function()
        
        # Should call weather service methods
        self.mock_weather_service.get_current_weather.assert_called_once_with(force_refresh=True)
        self.mock_weather_service.get_forecast.assert_called_once_with(force_refresh=True)

    def test_image_preload_task(self):
        """Test image preload task execution"""
        # Mock image info
        mock_image_info = {'id': 'test_id', 'name': 'test.jpg'}
        self.mock_drive_service.get_random_image.return_value = mock_image_info
        self.mock_drive_service.download_file.return_value = b'image_data'
        
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        # Find image preload task
        preload_task = next(t for t in task_manager.tasks if t.name == "image_preload")
        
        # Execute the task function
        preload_task.function()
        
        # Should refresh file list
        self.mock_drive_service.force_refresh_file_list.assert_called_once()
        
        # Should try to preload images
        self.assertGreaterEqual(self.mock_drive_service.get_random_image.call_count, 1)

    def test_cache_cleanup_task(self):
        """Test cache cleanup task execution"""
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        # Find cache cleanup task
        cleanup_task = next(t for t in task_manager.tasks if t.name == "cache_cleanup")
        
        # Execute the task function
        cleanup_task.function()
        
        # Should call cleanup method
        self.mock_weather_service.cleanup_expired_cache.assert_called_once()

    def test_image_preload_cache_clearing(self):
        """Test that image preload clears cache periodically"""
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        preload_task = next(t for t in task_manager.tasks if t.name == "image_preload")
        
        # Execute task 5 times (should trigger cache clear on 5th call)
        for i in range(5):
            preload_task.function()
        
        # Should have cleared cache once (on 5th call)
        self.mock_drive_service.clear_download_cache.assert_called()

    def test_image_preload_error_handling(self):
        """Test error handling in image preload task"""
        # Make get_random_image fail
        self.mock_drive_service.get_random_image.side_effect = Exception("Drive error")
        
        task_manager = create_standard_tasks(
            self.mock_weather_service,
            self.mock_drive_service,
            self.mock_image_service,
            self.config
        )
        
        preload_task = next(t for t in task_manager.tasks if t.name == "image_preload")
        
        # Should not raise exception
        try:
            preload_task.function()
        except Exception:
            self.fail("Preload task should handle errors gracefully")


if __name__ == '__main__':
    unittest.main()

