"""
Sprint 6: Formal joint constrained optimizer.
Reallocates fraud-loss budget across segments.
"""

import json
import itertools
from typing import Dict, List, Tuple
from src.threshold_optimizer import ThresholdOptimizer, CostModel
from src.churn_model import RealCostModel, ChurnModel

class JointOptimizer:
    """
    Joint constrained optimizer.
    Allocates fraud loss budget across segments to maximize total net benefit.
    """
    
    def __init__(self, cost_model_class=CostModel):
        self.cost_model_class = cost_model_class
        self.base_optimizer = ThresholdOptimizer()
    
    def load_outcomes(self, filepath: str) -> List[Dict]:
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def segment_outcomes(self, outcomes: List[Dict]) -> Dict[str, List[Dict]]:
        """Group outcomes by segment."""
        seg_groups = {}
        for tx in outcomes:
            seg = tx.get('segment_key', 'established|domestic')
            if seg not in seg_groups:
                seg_groups[seg] = []
            seg_groups[seg].append(tx)
        return seg_groups
    
    def compute_segment_efficiency(self, outcomes: List[Dict], segment: str) -> Dict:
        """
        Compute efficiency frontier for a segment:
        fraud_loss vs net_benefit for each threshold pair.
        """
        # Sweep thresholds for this segment
        thresholds = [round(x, 2) for x in [0.1 + i * 0.05 for i in range(18)]]
        results = []
        cost_model = self.cost_model_class(segment)
        
        for t_ch, t_de in itertools.product(thresholds, thresholds):
            if t_ch >= t_de:
                continue
            
            # Compute costs for this threshold pair
            total_cost = 0.0
            fraud_loss = 0.0
            approvals = 0
            total_transactions = len(outcomes)
            
            for tx in outcomes:
                score = tx.get('combined_risk_score', 0.5)
                is_fraud = tx.get('is_fraud', False)
                is_false_decline = tx.get('is_false_decline', False)
                churned = tx.get('churned_after_decline', False)
                amount = tx.get('amount', 100.0)
                
                if score < t_ch:
                    decision = 'APPROVE'
                    approvals += 1
                    if is_fraud:
                        cost = amount + 100.0  # fraud loss
                        fraud_loss += cost
                        total_cost += cost
                    else:
                        total_cost += 0  # correct approve
                elif score < t_de:
                    decision = 'CHALLENGE'
                    if is_fraud:
                        cost = (amount + 100.0) * 0.5
                        fraud_loss += cost * 0.5
                        total_cost += cost
                    elif is_false_decline:
                        cost = 50.0 * 0.3  # challenge friction cost
                        total_cost += cost
                    else:
                        total_cost += 10.0  # ops cost
                else:
                    decision = 'DECLINE'
                    if is_fraud:
                        total_cost += 0  # correctly blocked
                    elif is_false_decline:
                        # False decline cost depends on churn/CLV
                        if churned:
                            total_cost += 200.0  # placeholder CLV loss
                        else:
                            total_cost += 50.0
            
            # Net benefit = revenue from approvals - costs
            avg_revenue_per_approval = 10.0  # placeholder margin
            net_benefit = approvals * avg_revenue_per_approval - total_cost
            
            results.append({
                't_challenge': t_ch,
                't_decline': t_de,
                'fraud_loss': fraud_loss,
                'net_benefit': net_benefit,
                'approval_rate': approvals / max(1, total_transactions)
            })
        
        return results
    
    def allocate_budget(self, outcomes_by_segment: Dict[str, List[Dict]], total_fraud_ceiling: float) -> Dict[str, Tuple[float, float]]:
        """
        Allocate fraud loss budget across segments to maximize total net benefit.
        Uses greedy marginal allocation across segments.
        """
        # Build efficiency curves for each segment
        efficiency_curves = {}
        for seg, seg_outcomes in outcomes_by_segment.items():
            if len(seg_outcomes) < 5:
                continue
            efficiency_curves[seg] = self.compute_segment_efficiency(seg_outcomes, seg)
        
        # Greedy allocation: start with most permissive thresholds (low fraud loss)
        current_thresholds = {}
        current_fraud_loss = {}
        current_net_benefit = {}
        
        for seg, curves in efficiency_curves.items():
            # Start with lowest fraud loss option (most conservative)
            sorted_curves = sorted(curves, key=lambda x: x['fraud_loss'])
            best = sorted_curves[0]
            current_thresholds[seg] = (best['t_challenge'], best['t_decline'])
            current_fraud_loss[seg] = best['fraud_loss']
            current_net_benefit[seg] = best['net_benefit']
        
        # Allocate remaining budget to segments with highest marginal gain
        remaining_budget = total_fraud_ceiling - sum(current_fraud_loss.values())
        if remaining_budget <= 0:
            return current_thresholds
        
        # For each segment, compute marginal gain per unit fraud loss
        for seg, curves in efficiency_curves.items():
            if seg not in current_thresholds:
                continue
            
            sorted_curves = sorted(curves, key=lambda x: x['fraud_loss'])
            current_idx = 0
            for i, point in enumerate(sorted_curves):
                if abs(point['t_challenge'] - current_thresholds[seg][0]) < 0.01 and abs(point['t_decline'] - current_thresholds[seg][1]) < 0.01:
                    current_idx = i
                    break
            
            # Look at next points (more fraud, more net benefit)
            for i in range(current_idx + 1, len(sorted_curves)):
                marginal_fraud = sorted_curves[i]['fraud_loss'] - sorted_curves[current_idx]['fraud_loss']
                marginal_benefit = sorted_curves[i]['net_benefit'] - sorted_curves[current_idx]['net_benefit']
                
                if marginal_fraud <= 0 or marginal_benefit <= 0:
                    continue
                
                # If we have budget, move to this point
                if remaining_budget >= marginal_fraud:
                    current_thresholds[seg] = (sorted_curves[i]['t_challenge'], sorted_curves[i]['t_decline'])
                    current_fraud_loss[seg] = sorted_curves[i]['fraud_loss']
                    current_net_benefit[seg] = sorted_curves[i]['net_benefit']
                    remaining_budget -= marginal_fraud
                else:
                    # Partial allocation not supported in grid search
                    break
        
        return current_thresholds
    
    def optimize(self, outcomes_file: str, total_fraud_ceiling: float) -> Dict[str, Tuple[float, float]]:
        """Main entry point: optimize all segments jointly."""
        outcomes = self.load_outcomes(outcomes_file)
        outcomes_by_segment = self.segment_outcomes(outcomes)
        return self.allocate_budget(outcomes_by_segment, total_fraud_ceiling)