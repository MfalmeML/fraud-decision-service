"""
Sprint 1: Outcome feedback pipeline.
Captures false_decline and churned_after_decline signals.
"""

from datetime import datetime
from typing import Dict, Optional
import json
import os

# In-memory store for development. Replace with actual DB in Sprint 1.
OUTCOMES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "outcomes.json")

class OutcomeStore:
    def __init__(self):
        self._ensure_data_dir()
        self._outcomes = self._load()
    
    def _ensure_data_dir(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _load(self) -> Dict:
        if os.path.exists(OUTCOMES_FILE):
            with open(OUTCOMES_FILE, "r") as f:
                return json.load(f)
        return {}
    
    def _save(self):
        with open(OUTCOMES_FILE, "w") as f:
            json.dump(self._outcomes, f, indent=2)
    
    def record_outcome(self, transaction_id: str, label: str, value: bool, metadata: Optional[Dict] = None):
        """
        Records an outcome label for a transaction.
        Labels: 'is_fraud', 'is_false_decline', 'churned_after_decline'
        """
        if transaction_id not in self._outcomes:
            self._outcomes[transaction_id] = {}
        self._outcomes[transaction_id][label] = {
            "value": value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self._save()
    
    def get_outcome(self, transaction_id: str, label: str) -> Optional[bool]:
        return self._outcomes.get(transaction_id, {}).get(label, {}).get("value")
