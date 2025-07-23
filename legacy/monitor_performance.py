#!/usr/bin/env python3
"""
Performance monitoring script for PiFrame on Raspberry Pi
"""
import psutil
import time
import json
import os
from datetime import datetime

class PerformanceMonitor:
    """Class for monitoring system performance"""
    
    def __init__(self):
        self.stats_history = []
    
    def get_system_stats(self):
        """Get current system statistics"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_available': psutil.virtual_memory().available / (1024**3),  # GB
            'disk_usage': psutil.disk_usage('/').percent,
            'temperature': self.get_cpu_temperature(),
            'network_io': self.get_network_io()
        }
    
    def get_cpu_temperature(self):
        """Get CPU temperature (Raspberry Pi specific)"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
            return temp
        except:
            return None
    
    def get_network_io(self):
        """Get network I/O statistics"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv
            }
        except:
            return None
    
    def monitor_performance(self, duration_minutes=60, interval_seconds=30):
        """Monitor performance for specified duration"""
        stats = []
        end_time = time.time() + (duration_minutes * 60)
        
        print(f"Starting performance monitoring for {duration_minutes} minutes...")
        print("Press Ctrl+C to stop early")
        
        try:
            while time.time() < end_time:
                stat = self.get_system_stats()
                stats.append(stat)
                self.stats_history.append(stat)
                
                print(f"[{stat['timestamp']}] "
                      f"CPU: {stat['cpu_percent']:.1f}% "
                      f"Memory: {stat['memory_percent']:.1f}% "
                      f"Temp: {stat['temperature']:.1f}°C" if stat['temperature'] is not None else "Temp: N/A")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        
        # Save results
        filename = f"performance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"Performance data saved to {filename}")
        
        # Print summary
        if stats:
            cpu_avg = sum(s['cpu_percent'] for s in stats) / len(stats)
            mem_avg = sum(s['memory_percent'] for s in stats) / len(stats)
            
            # Handle temperature average safely
            temp_stats = [s for s in stats if s['temperature'] is not None]
            if temp_stats:
                temp_avg = sum(s['temperature'] for s in temp_stats) / len(temp_stats)
            else:
                temp_avg = None
            
            print(f"\nSummary:")
            print(f"Average CPU usage: {cpu_avg:.1f}%")
            print(f"Average memory usage: {mem_avg:.1f}%")
            if temp_avg is not None:
                print(f"Average temperature: {temp_avg:.1f}°C")
            else:
                print("Average temperature: N/A")
        
        return stats

# Legacy functions for backward compatibility
def get_system_stats():
    """Get current system statistics"""
    monitor = PerformanceMonitor()
    return monitor.get_system_stats()

def get_cpu_temperature():
    """Get CPU temperature (Raspberry Pi specific)"""
    monitor = PerformanceMonitor()
    return monitor.get_cpu_temperature()

def get_network_io():
    """Get network I/O statistics"""
    monitor = PerformanceMonitor()
    return monitor.get_network_io()

def monitor_performance(duration_minutes=60, interval_seconds=30):
    """Monitor performance for specified duration"""
    monitor = PerformanceMonitor()
    return monitor.monitor_performance(duration_minutes, interval_seconds)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor PiFrame performance')
    parser.add_argument('--duration', type=int, default=60, 
                       help='Monitoring duration in minutes (default: 60)')
    parser.add_argument('--interval', type=int, default=30,
                       help='Monitoring interval in seconds (default: 30)')
    
    args = parser.parse_args()
    
    monitor_performance(args.duration, args.interval) 