"""
Entry point for the fraud decision service.
Sprint 1: Outcome pipeline only.
"""

from src.outcome_store import OutcomeStore

if __name__ == "__main__":
    store = OutcomeStore()
    print("Outcome store initialized. Ready to record outcomes.")
    print("Example: store.record_outcome('tx123', 'is_false_decline', True)")
