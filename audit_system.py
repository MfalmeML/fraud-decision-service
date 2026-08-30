"""
System audit: Verify all components are present and working.
"""

import os
import json
import sys
from datetime import datetime

def audit_files():
    """Check all required files exist."""
    required = [
        "src/outcome_store.py",
        "src/outcome_api.py",
        "src/decision_engine.py",
        "src/threshold_optimizer.py",
        "src/reliability.py",
        "src/churn_model.py",
        "src/joint_optimizer.py",
        "src/server.py",
        "deploy/shadow_runner.py",
        "deploy/pilot_runner.py",
        "deploy/full_rollout.py",
        "data/sample_outcomes.json",
        "data/decline_outcomes.json",
        "data/historical_transactions.json"
    ]
    
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        print("MISSING FILES:")
        for f in missing:
            print(f"  {f}")
        return False
    
    print("All required files present.")
    return True

def audit_imports():
    """Verify all modules import correctly."""
    try:
        from src.outcome_store import OutcomeStore
        from src.decision_engine import DecisionEngine
        from src.threshold_optimizer import ThresholdOptimizer
        from src.reliability import ThresholdTableManager
        from src.churn_model import ChurnModel, RealCostModel
        from src.joint_optimizer import JointOptimizer
        from src.server import DecisionServer
        print("All imports succeed.")
        return True
    except ImportError as e:
        print(f"Import error: {e}")
        return False

def audit_instantiation():
    """Verify all components instantiate correctly."""
    try:
        from src.outcome_store import OutcomeStore
        from src.decision_engine import DecisionEngine
        from src.threshold_optimizer import ThresholdOptimizer
        from src.reliability import ThresholdTableManager
        from src.churn_model import ChurnModel, RealCostModel
        from src.joint_optimizer import JointOptimizer
        from src.server import DecisionServer
        
        store = OutcomeStore()
        engine = DecisionEngine()
        optimizer = ThresholdOptimizer()
        manager = ThresholdTableManager()
        churn = ChurnModel()
        joint = JointOptimizer()
        server = DecisionServer()
        
        print("All components instantiate successfully.")
        return True
    except Exception as e:
        print(f"Instantiation error: {e}")
        return False

def audit_thresholds():
    """Verify thresholds are accessible."""
    from src.reliability import ThresholdTableManager
    mgr = ThresholdTableManager()
    
    segments = ["new|domestic", "established|domestic", "vip|cross_border"]
    for seg in segments:
        t_ch, t_de = mgr.lookup(seg)
        if t_ch is None or t_de is None:
            print(f"Threshold lookup failed for {seg}")
            return False
        if not (0 <= t_ch <= 1 and 0 <= t_de <= 1):
            print(f"Invalid thresholds for {seg}: {t_ch}, {t_de}")
            return False
    print("Threshold lookups valid.")
    return True

def main():
    print("SYSTEM AUDIT")
    print("=" * 60)
    
    checks = [
        ("Files exist", audit_files),
        ("Imports work", audit_imports),
        ("Instantiation works", audit_instantiation),
        ("Thresholds valid", audit_thresholds)
    ]
    
    all_passed = True
    for name, func in checks:
        print(f"\nChecking: {name}")
        passed = func()
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("SYSTEM AUDIT PASSED")
        print("All components are present and functional.")
        print("Ready for production.")
    else:
        print("SYSTEM AUDIT FAILED")
        print("Fix identified issues before deployment.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())