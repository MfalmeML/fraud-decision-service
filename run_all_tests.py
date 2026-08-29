"""
Run all tests across the complete system.
"""

import sys
import os
import json
import subprocess
from datetime import datetime

def run_test_script(name: str, script: str) -> bool:
    """Run a test script and return success status."""
    print(f"\n=== {name} ===")
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Run all test suites."""
    print("FRAUD DECISION SERVICE - FULL TEST SUITE")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("=" * 60)
    
    tests = [
        ("Decision Engine", "test_decision_engine.py"),
        ("Threshold Optimizer", "test_optimizer.py"),
        ("Reliability Layer", "test_reliability.py"),
        ("Churn Model", "test_churn_model.py"),
        ("Joint Optimizer", "test_joint_optimizer.py"),
    ]
    
    results = []
    all_passed = True
    
    for name, script in tests:
        passed = run_test_script(name, script)
        results.append((name, passed))
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY:")
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
    
    if all_passed:
        print("\nALL TESTS PASSED")
    else:
        print("\nSOME TESTS FAILED")
    
    print(f"Completed: {datetime.utcnow().isoformat()}")
    
    # Write results to file
    with open("test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "all_passed": all_passed,
            "results": results
        }, f, indent=2)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())