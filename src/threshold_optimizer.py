"""
Sprint 2: Coarse cost model + grid search thresholds.
"""

import json
import os
from typing import Dict, List, Tuple
import itertools

class CostModel:
    """Cost of decision outcomes. Sprint 2 uses placeholder constants."""
    
    def __init__(self, segment: str):
        # Placeholder constants from specs.
        # Will be replaced with real churn/CLV models in Sprint 5.
        self.params = {
            "new|domestic": {"fn_cost": 100.0, "fp_cost": 50.0, "ch_cost": 10.0},
            "new|cross_border": {"fn_cost": 200.0, "fp_cost": 80.0, "ch_cost": 15.0},
            "established|domestic": {"fn_cost": 150.0, "fp_cost": 120.0, "ch_cost": 20.0},
            "established|cross_border": {"fn_cost": 300.0, "fp_cost": 200.0, "ch_cost": 30.0},
            "vip|domestic": {"fn_cost": 500.0, "fp_cost": 1000.0, "ch_cost": 50.0},
            "vip|cross_border": {"fn_cost": 800.0, "fp_cost": 1500.0, "ch_cost": 80.0},
        }.get(segment, {"fn_cost": 100.0, "fp_cost": 50.0, "ch_cost": 10.0})
    
    def cost_of_approve(self, is_fraud: bool, is_challenge: bool = False) -> float:
        """Cost if we approved this transaction."""
        if is_fraud:
            return self.params["fn_cost"]
        return 0.0
    
    def cost_of_decline(self, is_fraud: bool, is_false_decline: bool, churned: bool) -> float:
        """Cost if we declined this transaction."""
        if is_fraud:
            return 0.0  # Correctly blocked fraud
        if is_false_decline:
            return self.params["fp_cost"] * (1.5 if churned else 1.0)
        return 0.0
    
    def cost_of_challenge(self, is_fraud: bool, is_false_decline: bool, churned: bool) -> float:
        """Cost if we challenged this transaction."""
        if is_fraud:
            return self.params["fn_cost"] * 0.5  # Might catch some
        if is_false_decline:
            return self.params["fp_cost"] * 0.3  # Less severe than decline
        return self.params["ch_cost"]


class ThresholdOptimizer:
    """Grid search over threshold pairs per segment."""
    
    def __init__(self, cost_model_class=CostModel):
        self.cost_model_class = cost_model_class
    
    def load_outcomes(self, filepath: str) -> List[Dict]:
        """Load historical labeled outcomes."""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def evaluate_threshold(self, outcomes: List[Dict], t_challenge: float, t_decline: float, segment: str) -> Dict:
        """Compute total cost and fraud loss for given thresholds."""
        cost_model = self.cost_model_class(segment)
        total_cost = 0.0
        fraud_loss = 0.0
        decisions = []
        
        for tx in outcomes:
            score = tx.get('combined_risk_score', 0.5)
            is_fraud = tx.get('is_fraud', False)
            is_false_decline = tx.get('is_false_decline', False)
            churned = tx.get('churned_after_decline', False)
            
            # Decision
            if score < t_challenge:
                decision = 'APPROVE'
                cost = cost_model.cost_of_approve(is_fraud)
                if is_fraud:
                    fraud_loss += cost
            elif score < t_decline:
                decision = 'CHALLENGE'
                cost = cost_model.cost_of_challenge(is_fraud, is_false_decline, churned)
                if is_fraud:
                    fraud_loss += cost * 0.5
            else:
                decision = 'DECLINE'
                cost = cost_model.cost_of_decline(is_fraud, is_false_decline, churned)
            
            total_cost += cost
            decisions.append(decision)
        
        approval_rate = sum(1 for d in decisions if d == 'APPROVE') / len(decisions)
        challenge_rate = sum(1 for d in decisions if d == 'CHALLENGE') / len(decisions)
        decline_rate = sum(1 for d in decisions if d == 'DECLINE') / len(decisions)
        
        return {
            'total_cost': total_cost,
            'fraud_loss': fraud_loss,
            'approval_rate': approval_rate,
            'challenge_rate': challenge_rate,
            'decline_rate': decline_rate,
        }
    
    def grid_search(self, outcomes: List[Dict], segment: str, fraud_ceiling: float = 1000.0) -> Tuple[float, float]:
        """Sweep thresholds, pick best under fraud loss ceiling."""
        thresholds = [round(x, 2) for x in [0.1 + i * 0.05 for i in range(18)]]
        best_t_challenge, best_t_decline = 0.50, 0.88
        best_cost = float('inf')
        
        for t_ch, t_de in itertools.product(thresholds, thresholds):
            if t_ch >= t_de:
                continue
            result = self.evaluate_threshold(outcomes, t_ch, t_de, segment)
            if result['fraud_loss'] <= fraud_ceiling:
                if result['total_cost'] < best_cost:
                    best_cost = result['total_cost']
                    best_t_challenge, best_t_decline = t_ch, t_de
        
        return best_t_challenge, best_t_decline
    
    def optimize_all_segments(self, outcomes_file: str, fraud_ceiling: float = 1000.0) -> Dict:
        """Generate threshold table for all segments."""
        outcomes = self.load_outcomes(outcomes_file)
        segments = set(tx.get('segment_key', 'established|domestic') for tx in outcomes)
        table = {}
        for seg in segments:
            seg_outcomes = [tx for tx in outcomes if tx.get('segment_key') == seg]
            if len(seg_outcomes) < 10:
                # Fallback to parent segment
                parent = seg.split('|')[0] + '|domestic'
                seg_outcomes = [tx for tx in outcomes if tx.get('segment_key') == parent]
            t_ch, t_de = self.grid_search(seg_outcomes, seg, fraud_ceiling)
            table[seg] = (t_ch, t_de)
        return table