#!/usr/bin/env python3
"""
Test runner script for the changelog generator.

This script provides convenient ways to run different test suites and
generate reports. It's designed to be used both locally and in CI/CD.
"""

import argparse
import sys
import subprocess
import os
from pathlib import Path


def run_command(command, description=""):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description or command}")
    print('='*60)
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=False,
            text=True
        )
        print(f"✅ {description or command} completed successfully")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or command} failed with exit code {e.returncode}")
        return False


def setup_environment():
    """Set up the test environment."""
    # Add current directory to Python path
    current_dir = Path(__file__).parent.absolute()
    os.environ['PYTHONPATH'] = str(current_dir)
    
    # Create necessary directories
    (current_dir / 'test_results').mkdir(exist_ok=True)
    (current_dir / 'coverage_reports').mkdir(exist_ok=True)


def run_unit_tests(verbose=False, coverage=True):
    """Run unit tests."""
    cmd = "pytest tests/unit/"
    
    if verbose:
        cmd += " -v"
    
    if coverage:
        cmd += " --cov=. --cov-report=html:coverage_reports/unit --cov-report=xml:coverage_reports/unit_coverage.xml"
    
    cmd += " --junitxml=test_results/unit_results.xml"
    
    return run_command(cmd, "Unit Tests")


def run_integration_tests(verbose=False, coverage=True):
    """Run integration tests."""
    cmd = "pytest tests/integration/"
    
    if verbose:
        cmd += " -v"
    
    if coverage:
        cmd += " --cov=. --cov-append --cov-report=html:coverage_reports/integration --cov-report=xml:coverage_reports/integration_coverage.xml"
    
    cmd += " --junitxml=test_results/integration_results.xml"
    
    return run_command(cmd, "Integration Tests")


def run_security_tests(verbose=False):
    """Run security tests."""
    cmd = "pytest tests/security/ -m security"
    
    if verbose:
        cmd += " -v"
    
    cmd += " --junitxml=test_results/security_results.xml"
    
    return run_command(cmd, "Security Tests")


def run_performance_tests(verbose=False, benchmark=False):
    """Run performance tests."""
    cmd = "pytest tests/performance/ -m performance"
    
    if verbose:
        cmd += " -v"
    
    if benchmark:
        cmd += " --benchmark-json=test_results/benchmark_results.json"
    
    cmd += " --junitxml=test_results/performance_results.xml"
    
    return run_command(cmd, "Performance Tests")


def run_edge_case_tests(verbose=False):
    """Run edge case tests."""
    cmd = "pytest tests/unit/test_edge_cases.py"
    
    if verbose:
        cmd += " -v"
    
    cmd += " --junitxml=test_results/edge_case_results.xml"
    
    return run_command(cmd, "Edge Case Tests")


def run_all_tests(verbose=False, coverage=True, benchmark=False):
    """Run all test suites."""
    results = []
    
    results.append(run_unit_tests(verbose, coverage))
    results.append(run_integration_tests(verbose, coverage))
    results.append(run_security_tests(verbose))
    results.append(run_performance_tests(verbose, benchmark))
    results.append(run_edge_case_tests(verbose))
    
    return all(results)


def run_quick_tests(verbose=False):
    """Run a quick subset of tests for development."""
    cmd = "pytest tests/unit/ tests/integration/ -m 'not slow and not performance'"
    
    if verbose:
        cmd += " -v"
    
    cmd += " --maxfail=5 --tb=short"
    
    return run_command(cmd, "Quick Tests (excluding slow tests)")


def run_coverage_report():
    """Generate comprehensive coverage report."""
    cmd = "pytest tests/ --cov=. --cov-report=html:coverage_reports/full --cov-report=xml:coverage_reports/full_coverage.xml --cov-report=term-missing"
    
    return run_command(cmd, "Full Coverage Report")


def run_linting():
    """Run code linting and quality checks."""
    commands = [
        ("flake8 . --max-line-length=127 --extend-ignore=E203,W503", "Flake8 Linting"),
        ("black --check --diff .", "Black Code Formatting Check"),
        ("isort --check-only --diff .", "Import Sorting Check"),
    ]
    
    results = []
    for cmd, desc in commands:
        try:
            results.append(run_command(cmd, desc))
        except:
            # If tools not installed, skip
            print(f"⚠️  Skipping {desc} - tool not installed")
            results.append(True)
    
    return all(results)


def run_security_scan():
    """Run security scanning tools."""
    commands = [
        ("bandit -r . -f txt", "Bandit Security Scan"),
        ("safety check", "Safety Vulnerability Check"),
    ]
    
    results = []
    for cmd, desc in commands:
        try:
            results.append(run_command(cmd, desc))
        except:
            print(f"⚠️  Skipping {desc} - tool not installed")
            results.append(True)
    
    return all(results)


def generate_test_report():
    """Generate a comprehensive test report."""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST REPORT")
    print("="*80)
    
    # Check for test result files
    results_dir = Path("test_results")
    coverage_dir = Path("coverage_reports")
    
    if results_dir.exists():
        result_files = list(results_dir.glob("*.xml"))
        print(f"\nTest Result Files ({len(result_files)}):")
        for file in result_files:
            print(f"  - {file}")
    
    if coverage_dir.exists():
        coverage_files = list(coverage_dir.glob("**/*.html")) + list(coverage_dir.glob("**/*.xml"))
        print(f"\nCoverage Report Files ({len(coverage_files)}):")
        for file in coverage_files:
            print(f"  - {file}")
    
    # Display coverage summary if available
    full_coverage = coverage_dir / "full_coverage.xml"
    if full_coverage.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(full_coverage)
            root = tree.getroot()
            
            coverage_elem = root.find('.//coverage')
            if coverage_elem is not None:
                line_rate = coverage_elem.get('line-rate', '0')
                branch_rate = coverage_elem.get('branch-rate', '0')
                
                print(f"\nOverall Coverage:")
                print(f"  - Line Coverage: {float(line_rate)*100:.1f}%")
                print(f"  - Branch Coverage: {float(branch_rate)*100:.1f}%")
        except:
            print("\n⚠️  Could not parse coverage data")
    
    print("\n" + "="*80)


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description="Test runner for the Changelog Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py --all                    # Run all tests
  python run_tests.py --unit --verbose         # Run unit tests with verbose output
  python run_tests.py --quick                  # Run quick tests for development
  python run_tests.py --security --linting     # Run security tests and linting
  python run_tests.py --coverage-report        # Generate full coverage report
        """
    )
    
    # Test suite options
    parser.add_argument('--all', action='store_true', help='Run all test suites')
    parser.add_argument('--unit', action='store_true', help='Run unit tests')
    parser.add_argument('--integration', action='store_true', help='Run integration tests')
    parser.add_argument('--security', action='store_true', help='Run security tests')
    parser.add_argument('--performance', action='store_true', help='Run performance tests')
    parser.add_argument('--edge-cases', action='store_true', help='Run edge case tests')
    parser.add_argument('--quick', action='store_true', help='Run quick tests (excluding slow ones)')
    
    # Quality checks
    parser.add_argument('--linting', action='store_true', help='Run linting and code quality checks')
    parser.add_argument('--security-scan', action='store_true', help='Run security scanning tools')
    
    # Reports
    parser.add_argument('--coverage-report', action='store_true', help='Generate comprehensive coverage report')
    parser.add_argument('--test-report', action='store_true', help='Generate test summary report')
    
    # Options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--no-coverage', action='store_true', help='Skip coverage reporting')
    parser.add_argument('--benchmark', action='store_true', help='Include benchmark results')
    parser.add_argument('--fail-fast', action='store_true', help='Stop on first test failure')
    
    args = parser.parse_args()
    
    # If no specific tests are requested, show help
    if not any([
        args.all, args.unit, args.integration, args.security, 
        args.performance, args.edge_cases, args.quick,
        args.linting, args.security_scan, args.coverage_report, args.test_report
    ]):
        parser.print_help()
        return 1
    
    # Set up environment
    setup_environment()
    
    results = []
    
    try:
        if args.coverage_report:
            results.append(run_coverage_report())
        
        if args.linting:
            results.append(run_linting())
        
        if args.security_scan:
            results.append(run_security_scan())
        
        if args.all:
            results.append(run_all_tests(args.verbose, not args.no_coverage, args.benchmark))
        else:
            if args.unit:
                results.append(run_unit_tests(args.verbose, not args.no_coverage))
            
            if args.integration:
                results.append(run_integration_tests(args.verbose, not args.no_coverage))
            
            if args.security:
                results.append(run_security_tests(args.verbose))
            
            if args.performance:
                results.append(run_performance_tests(args.verbose, args.benchmark))
            
            if args.edge_cases:
                results.append(run_edge_case_tests(args.verbose))
            
            if args.quick:
                results.append(run_quick_tests(args.verbose))
        
        if args.test_report:
            generate_test_report()
        
        # Summary
        if results:
            passed = sum(results)
            total = len(results)
            
            print(f"\n{'='*60}")
            print(f"TEST SUMMARY: {passed}/{total} test suites passed")
            print('='*60)
            
            if passed == total:
                print("🎉 All tests passed!")
                return 0
            else:
                print(f"❌ {total - passed} test suite(s) failed")
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test run interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\n❌ Test runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())