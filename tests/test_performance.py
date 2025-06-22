"""
Tests for performance monitoring and optimization
"""
import unittest
import time
import tempfile
import os
import json
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monitor_performance


class TestPerformanceMonitoring(unittest.TestCase):
    """Test cases for performance monitoring"""

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = monitor_performance.PerformanceMonitor()

    def tearDown(self):
        """Clean up after tests"""
        pass

    def test_system_stats(self):
        """Test system statistics gathering"""
        stats = self.monitor.get_system_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('timestamp', stats)
        self.assertIn('cpu_percent', stats)
        self.assertIn('memory_percent', stats)
        self.assertIn('memory_available', stats)
        self.assertIn('disk_usage', stats)
        self.assertIn('temperature', stats)
        self.assertIn('network_io', stats)
        
        # Values should be reasonable
        self.assertGreaterEqual(stats['cpu_percent'], 0)
        self.assertLessEqual(stats['cpu_percent'], 100)
        self.assertGreaterEqual(stats['memory_percent'], 0)
        self.assertLessEqual(stats['memory_percent'], 100)
        self.assertGreaterEqual(stats['disk_usage'], 0)
        self.assertLessEqual(stats['disk_usage'], 100)

    @patch('monitor_performance.psutil.cpu_percent')
    def test_cpu_percent(self, mock_cpu_percent):
        """Test CPU percentage calculation"""
        mock_cpu_percent.return_value = 25.5
        
        stats = self.monitor.get_system_stats()
        self.assertEqual(stats['cpu_percent'], 25.5)

    @patch('monitor_performance.psutil.virtual_memory')
    def test_memory_stats(self, mock_virtual_memory):
        """Test memory statistics"""
        mock_memory = MagicMock()
        mock_memory.percent = 65.2
        mock_memory.available = 2 * 1024**3  # 2 GB
        mock_virtual_memory.return_value = mock_memory
        
        stats = self.monitor.get_system_stats()
        self.assertEqual(stats['memory_percent'], 65.2)
        self.assertEqual(stats['memory_available'], 2.0)

    @patch('monitor_performance.psutil.disk_usage')
    def test_disk_usage(self, mock_disk_usage):
        """Test disk usage calculation"""
        mock_disk = MagicMock()
        mock_disk.percent = 45.8
        mock_disk_usage.return_value = mock_disk
        
        stats = self.monitor.get_system_stats()
        self.assertEqual(stats['disk_usage'], 45.8)

    @patch('builtins.open', new_callable=mock_open, read_data='45000')
    def test_cpu_temperature_raspberry_pi(self, mock_file):
        """Test CPU temperature reading on Raspberry Pi"""
        temp = self.monitor.get_cpu_temperature()
        self.assertEqual(temp, 45.0)
        mock_file.assert_called_once_with('/sys/class/thermal/thermal_zone0/temp', 'r')

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_cpu_temperature_not_raspberry_pi(self, mock_file):
        """Test CPU temperature when not on Raspberry Pi"""
        temp = self.monitor.get_cpu_temperature()
        self.assertIsNone(temp)

    @patch('monitor_performance.psutil.net_io_counters')
    def test_network_io(self, mock_net_io):
        """Test network I/O statistics"""
        mock_io = MagicMock()
        mock_io.bytes_sent = 1024 * 1024  # 1 MB
        mock_io.bytes_recv = 2048 * 1024  # 2 MB
        mock_net_io.return_value = mock_io
        
        network_io = self.monitor.get_network_io()
        self.assertEqual(network_io['bytes_sent'], 1024 * 1024)
        self.assertEqual(network_io['bytes_recv'], 2048 * 1024)

    @patch('monitor_performance.psutil.net_io_counters', side_effect=Exception)
    def test_network_io_error(self, mock_net_io):
        """Test network I/O when error occurs"""
        network_io = self.monitor.get_network_io()
        self.assertIsNone(network_io)

    def test_stats_history(self):
        """Test stats history tracking"""
        # Add some stats to history
        stats1 = {'timestamp': '2023-12-25T10:00:00', 'cpu_percent': 25.0}
        stats2 = {'timestamp': '2023-12-25T10:01:00', 'cpu_percent': 30.0}
        
        self.monitor.stats_history.append(stats1)
        self.monitor.stats_history.append(stats2)
        
        self.assertEqual(len(self.monitor.stats_history), 2)
        self.assertEqual(self.monitor.stats_history[0]['cpu_percent'], 25.0)
        self.assertEqual(self.monitor.stats_history[1]['cpu_percent'], 30.0)

    @patch('monitor_performance.time.sleep')
    @patch('monitor_performance.json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_monitor_performance_short_duration(self, mock_file, mock_json_dump, mock_sleep):
        """Test performance monitoring with short duration"""
        # Mock time.time to control the loop
        with patch('monitor_performance.time.time') as mock_time:
            mock_time.side_effect = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # More iterations
            
            stats = self.monitor.monitor_performance(duration_minutes=0.1, interval_seconds=1)
            
            # Should have collected some stats
            self.assertIsInstance(stats, list)
            self.assertGreater(len(stats), 0)

    @patch('monitor_performance.time.sleep')
    def test_monitor_performance_keyboard_interrupt(self, mock_sleep):
        """Test performance monitoring with keyboard interrupt"""
        mock_sleep.side_effect = KeyboardInterrupt()
        
        stats = self.monitor.monitor_performance(duration_minutes=60, interval_seconds=1)
        
        # Should return empty list on interrupt
        self.assertEqual(stats, [])

    def test_legacy_functions(self):
        """Test legacy function compatibility"""
        # Test that legacy functions still work
        stats = monitor_performance.get_system_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('timestamp', stats)
        
        temp = monitor_performance.get_cpu_temperature()
        # Should be None on non-Raspberry Pi systems
        self.assertIsInstance(temp, (float, type(None)))
        
        network_io = monitor_performance.get_network_io()
        self.assertIsInstance(network_io, (dict, type(None)))


if __name__ == '__main__':
    unittest.main() 