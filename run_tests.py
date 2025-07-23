#!/usr/bin/env python3
"""
Test runner for PiFrame application
"""
import unittest
import sys
import os
import argparse
import coverage
from io import StringIO

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_tests_with_coverage(test_pattern='test_*.py', coverage_report=True):
    """Run tests with coverage reporting"""
    if coverage_report:
        # Start coverage measurement
        cov = coverage.Coverage(
            source=['.', 'piframe'],
            omit=[
                '*/tests/*',
                '*/venv/*',
                '*/__pycache__/*',
                'run_tests.py',
                'start*.py',
                '*.pyc',
                'test_*.py',
                'setup.py',
                'monitor_performance.py'
            ]
        )
        cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern=test_pattern)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    if coverage_report:
        # Stop coverage and generate report
        cov.stop()
        cov.save()
        
        print("\n" + "="*60)
        print("COVERAGE REPORT")
        print("="*60)
        
        # Print coverage summary
        cov.report()
        
        # Generate HTML report
        cov.html_report(directory='htmlcov')
        print(f"\nHTML coverage report generated in 'htmlcov' directory")
    
    return result.wasSuccessful()


def run_specific_test(test_file):
    """Run a specific test file"""
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return False
    
    # Import and run the specific test
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.dirname(test_file), pattern=os.path.basename(test_file))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_unit_tests():
    """Run only unit tests"""
    return run_tests_with_coverage('test_*.py', coverage_report=False)


def run_integration_tests():
    """Run only integration tests"""
    return run_tests_with_coverage('tests/test_integration.py', coverage_report=False)


def run_performance_tests():
    """Run only performance tests"""
    return run_tests_with_coverage('tests/test_performance.py', coverage_report=False)


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='Run PiFrame tests')
    parser.add_argument(
        '--test-file', 
        help='Run a specific test file (e.g., tests/test_app.py)'
    )
    parser.add_argument(
        '--unit-only', 
        action='store_true', 
        help='Run only unit tests'
    )
    parser.add_argument(
        '--integration-only', 
        action='store_true', 
        help='Run only integration tests'
    )
    parser.add_argument(
        '--performance-only', 
        action='store_true', 
        help='Run only performance tests'
    )
    parser.add_argument(
        '--no-coverage', 
        action='store_true', 
        help='Run tests without coverage reporting'
    )
    parser.add_argument(
        '--pattern', 
        default='test_*.py',
        help='Test file pattern (default: test_*.py)'
    )
    
    args = parser.parse_args()
    
    print("PiFrame Test Runner")
    print("=" * 50)
    
    # Check if tests directory exists
    if not os.path.exists('tests'):
        print("Error: 'tests' directory not found!")
        print("Please run this script from the project root directory.")
        return 1
    
    try:
        if args.test_file:
            # Run specific test file
            print(f"Running specific test: {args.test_file}")
            success = run_specific_test(args.test_file)
        elif args.unit_only:
            # Run only unit tests
            print("Running unit tests only...")
            success = run_unit_tests()
        elif args.integration_only:
            # Run only integration tests
            print("Running integration tests only...")
            success = run_integration_tests()
        elif args.performance_only:
            # Run only performance tests
            print("Running performance tests only...")
            success = run_performance_tests()
        else:
            # Run all tests
            print("Running all tests...")
            success = run_tests_with_coverage(
                args.pattern, 
                coverage_report=not args.no_coverage
            )
        
        print("\n" + "=" * 50)
        if success:
            print("✅ All tests passed!")
            return 0
        else:
            print("❌ Some tests failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nTest run interrupted by user")
        return 1
    except Exception as e:
        print(f"\nError running tests: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main()) 