#!/usr/bin/env python3
"""
Script to test CI/CD setup locally before pushing to GitHub.
Mimics the GitHub Actions workflows to catch issues early.
"""

import subprocess
import sys
import os
import time
from pathlib import Path

def run_command(cmd, description, critical=True, timeout=300):
    """Run a command and report results."""
    print(f"\n🔄 {description}")
    print(f"   Command: {cmd}")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=Path(__file__).parent.parent
        )
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"   ✅ PASSED ({duration:.1f}s)")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()[:200]}...")
            return True
        else:
            print(f"   ❌ FAILED ({duration:.1f}s)")
            if result.stderr.strip():
                print(f"   Error: {result.stderr.strip()[:200]}...")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()[:200]}...")
            
            if critical:
                return False
            else:
                print(f"   ⚠️  Non-critical failure, continuing...")
                return True
                
    except subprocess.TimeoutExpired:
        print(f"   ⏰ TIMEOUT after {timeout}s")
        return not critical
    except Exception as e:
        print(f"   💥 ERROR: {e}")
        return not critical

def check_environment():
    """Check that the environment is set up correctly."""
    print("🔍 Checking Environment Setup")
    
    # Check Python version
    python_version = sys.version_info
    print(f"   Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 9):
        print("   ❌ Python 3.9+ required")
        return False
    
    # Check required files exist
    required_files = [
        'requirements.txt',
        'scripts/run_tests.py',
        'piframe/__init__.py',
        'tests/test_cache_manager.py',
        'tests/test_weather_service.py',
        '.github/workflows/tests.yml'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} exists")
        else:
            print(f"   ❌ {file_path} missing")
            return False
    
    return True

def test_imports():
    """Test that all critical imports work."""
    print("\n🔍 Testing Core Imports")
    
    import_tests = [
        "from piframe.config.settings import Config",
        "from piframe.models.cache import CacheManager, TTLCache",
        "from piframe.services.weather_service import WeatherService",
        "from piframe.services.drive_service import DriveService",
        "from piframe.services.image_service import ImageService",
        "from piframe.utils.metadata import extract_image_metadata"
    ]
    
    for import_test in import_tests:
        cmd = f'python3 -c "{import_test}; print(\'✅ {import_test}\')"'
        if not run_command(cmd, f"Import: {import_test}", critical=True, timeout=30):
            return False
    
    return True

def test_basic_functionality():
    """Test basic functionality works."""
    print("\n🔍 Testing Basic Functionality")
    
    functionality_test = '''
import sys, os
sys.path.insert(0, ".")

# Test configuration
from piframe.config.settings import Config
config = Config()
print("Config created")

# Test cache manager
from piframe.models.cache import CacheManager
cache_manager = CacheManager(config)
cache_manager.set("test", "key", "value")
assert cache_manager.get("test", "key") == "value"
print("Cache manager works")

# Test weather service
from piframe.services.weather_service import WeatherService
weather_service = WeatherService(config, cache_manager)
celsius = weather_service.to_celsius(293.15)
assert celsius == 20.0
print("Weather service works")

print("All basic functionality tests passed")
'''
    
    return run_command(
        f'python3 -c "{functionality_test}"',
        "Basic functionality test",
        critical=True,
        timeout=60
    )

def run_critical_tests():
    """Run the most critical unit tests."""
    print("\n🔍 Running Critical Unit Tests")
    
    critical_tests = [
        "tests.test_cache_manager.TestTTLCache.test_set_and_get_basic",
        "tests.test_cache_manager.TestCacheManager.test_get_set_delete_operations", 
        "tests.test_weather_service.TestWeatherService.test_init",
        "tests.test_weather_service.TestWeatherService.test_to_celsius",
        "tests.test_drive_service.TestDriveService.test_init",
        "tests.test_image_service.TestImageService.test_init"
    ]
    
    for test in critical_tests:
        if not run_command(
            f"python3 -m unittest {test} -v",
            f"Unit test: {test.split('.')[-1]}",
            critical=True,
            timeout=60
        ):
            return False
    
    return True

def run_performance_check():
    """Run performance baseline check."""
    print("\n🔍 Performance Baseline Check")
    
    perf_test = '''
import sys, time
sys.path.insert(0, ".")
from piframe.models.cache import TTLCache

# Performance test
start_time = time.time()
cache = TTLCache(max_size=1000, default_ttl=60)

for i in range(1000):
    cache.set("key_" + str(i), "value_" + str(i))
    cache.get("key_" + str(i))

end_time = time.time()
duration = end_time - start_time
ops_per_sec = 2000 / duration

print("Performance: " + str(int(ops_per_sec)) + " ops/sec (" + str(round(duration, 3)) + "s for 2000 ops)")

if ops_per_sec < 1000:
    print("Performance below baseline")
else:
    print("Performance acceptable")
'''
    
    return run_command(
        f'python3 -c "{perf_test}"',
        "Performance baseline check",
        critical=False,
        timeout=30
    )

def run_syntax_check():
    """Check syntax of all Python files."""
    print("\n🔍 Syntax Check")
    
    return run_command(
        "python3 -m py_compile piframe/**/*.py",
        "Syntax check for modular code",
        critical=True,
        timeout=30
    )

def main():
    """Main test runner."""
    print("🚀 PiFrame CI/CD Setup Test")
    print("=" * 50)
    
    start_time = time.time()
    
    # Run all checks
    checks = [
        ("Environment Setup", check_environment),
        ("Core Imports", test_imports), 
        ("Basic Functionality", test_basic_functionality),
        ("Critical Unit Tests", run_critical_tests),
        ("Performance Check", run_performance_check),
        ("Syntax Check", run_syntax_check)
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        print(f"\n{'='*20} {check_name} {'='*20}")
        results[check_name] = check_func()
    
    # Summary
    end_time = time.time()
    total_duration = end_time - start_time
    
    print(f"\n{'='*50}")
    print("📊 SUMMARY")
    print(f"{'='*50}")
    print(f"Total duration: {total_duration:.1f}s")
    print()
    
    passed = 0
    failed = 0
    
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:<10} {check_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All checks passed! Ready for GitHub Actions.")
        print("\nNext steps:")
        print("  1. git add .")
        print("  2. git commit -m 'Add comprehensive test suite and CI/CD'")
        print("  3. git push")
        print("  4. Check GitHub Actions: https://github.com/YOUR_USERNAME/piframe/actions")
        return 0
    else:
        print(f"\n⚠️  {failed} checks failed. Fix issues before pushing.")
        return 1

if __name__ == "__main__":
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    sys.exit(main())