"""
Sprint 4: Reliability layer.
Fallback logic, canary gate, version management.
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Dict, Tuple, Optional
from threading import Lock

class ThresholdTableManager:
    """Manages versioned threshold tables with fallback and canary validation."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.lock = Lock()
        self._ensure_config_dir()
        
        # Current live table
        self.current_version = None
        self.current_table = None
        
        # Last known good (LKG) fallback
        self.lkg_version = None
        self.lkg_table = None
        
        # Load initial state
        self._load_latest()
    
    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
    
    def _load_latest(self):
        """Load the latest valid table from disk."""
        version_file = os.path.join(self.config_dir, "current_version.txt")
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()
            table_file = os.path.join(self.config_dir, f"table_{version}.json")
            if os.path.exists(table_file):
                with open(table_file, 'r') as f:
                    self.current_table = json.load(f)
                    self.current_version = version
                    self.lkg_version = version
                    self.lkg_table = self.current_table.copy()
                    return
        
        # No valid table found - load hardcoded defaults
        self.current_table = self._default_table()
        self.current_version = "initial-default"
        self.lkg_table = self.current_table.copy()
        self.lkg_version = self.current_version
    
    def _default_table(self) -> Dict:
        """Fallback defaults if no persisted table exists."""
        return {
            "new|domestic": [0.40, 0.85],
            "new|cross_border": [0.30, 0.75],
            "established|domestic": [0.55, 0.90],
            "established|cross_border": [0.45, 0.85],
            "vip|domestic": [0.65, 0.95],
            "vip|cross_border": [0.55, 0.90],
        }
    
    def lookup(self, segment_key: str) -> Tuple[float, float]:
        """Get threshold pair for segment. Falls back to coarser segment if missing."""
        with self.lock:
            table = self.current_table
            if not table:
                table = self.lkg_table
            
            if segment_key in table:
                t_ch, t_de = table[segment_key]
                return t_ch, t_de
            
            # Fallback to parent segment (tier|domestic)
            parts = segment_key.split('|')
            if len(parts) >= 2:
                parent = f"{parts[0]}|domestic"
                if parent in table:
                    return table[parent][0], table[parent][1]
            
            # Ultimate fallback to fixed defaults
            return 0.50, 0.88
    
    def get_version(self) -> str:
        return self.current_version
    
    def lkg_version(self) -> str:
        return self.lkg_version
    
    def is_stale(self) -> bool:
        """Check if current table is older than 7 days."""
        if not self.current_version or self.current_version == "initial-default":
            return False
        # Parse version timestamp: format "2026-08-28T00:00Z-v1"
        try:
            ts_str = self.current_version.split('-v')[0]
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            age = (datetime.now().astimezone() - ts).days
            return age > 7
        except:
            return False
    
    def backtest_validate(self, candidate_table: Dict, historical_outcomes_file: str, fraud_ceiling: float) -> bool:
        """
        Canary gate: replay candidate against historical data.
        Returns True if fraud loss stays within ceiling.
        """
        try:
            from src.threshold_optimizer import ThresholdOptimizer
        except ImportError:
            # Fallback when src/ itself is on sys.path (bare-import style, as in outcome_api.py)
            from threshold_optimizer import ThresholdOptimizer
        optimizer = ThresholdOptimizer()
        
        try:
            with open(historical_outcomes_file, 'r') as f:
                outcomes = json.load(f)
        except:
            # No historical data - cannot validate, reject
            return False
        
        # Compute fraud loss for candidate table
        total_fraud_loss = 0.0
        for tx in outcomes:
            score = tx.get('combined_risk_score', 0.5)
            seg = tx.get('segment_key', 'established|domestic')
            t_ch, t_de = candidate_table.get(seg, (0.50, 0.88))
            
            if score < t_ch:
                decision = 'APPROVE'
            elif score < t_de:
                decision = 'CHALLENGE'
            else:
                decision = 'DECLINE'
            
            if tx.get('is_fraud', False):
                if decision == 'APPROVE':
                    total_fraud_loss += tx.get('amount', 100.0)
                elif decision == 'CHALLENGE':
                    total_fraud_loss += tx.get('amount', 100.0) * 0.5
        
        return total_fraud_loss <= fraud_ceiling
    
    def publish_table(self, table: Dict, version: str, historical_outcomes_file: str = None, fraud_ceiling: float = None) -> bool:
        """
        Publish new threshold table. Runs canary gate if validation data provided.
        """
        # Sanitize the version: it becomes part of the table filename, and Windows
        # forbids <>:"/\|?* in filenames (e.g. colons from ISO timestamps).
        version = re.sub(r'[<>:"/\\|?*]', '-', str(version))

        # Validate if we have historical data
        if historical_outcomes_file and fraud_ceiling is not None:
            if not self.backtest_validate(table, historical_outcomes_file, fraud_ceiling):
                return False
        
        with self.lock:
            # Save table
            table_file = os.path.join(self.config_dir, f"table_{version}.json")
            with open(table_file, 'w') as f:
                json.dump(table, f, indent=2)
            
            # Update current
            self.current_table = table
            self.current_version = version
            
            # Update LKG (this passed validation, so it's good)
            self.lkg_table = table.copy()
            self.lkg_version = version
            
            # Save version pointer
            version_file = os.path.join(self.config_dir, "current_version.txt")
            with open(version_file, 'w') as f:
                f.write(version)
            
            return True
    
    def rollback_to_lkg(self) -> bool:
        """Revert to last known good table."""
        with self.lock:
            if self.lkg_table:
                self.current_table = self.lkg_table.copy()
                self.current_version = self.lkg_version
                return True
            return False
    
    def fallback_to_lkg(self) -> bool:
        """Alias for rollback_to_lkg - used when table is stale/unreachable."""
        return self.rollback_to_lkg()