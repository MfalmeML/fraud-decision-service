"""
Sprint 5: Real cost-model inputs.
Fits churn/CLV estimator per segment on accumulated decline-outcome data.
"""

import json
import os
from typing import Dict, List, Tuple, Optional
import math
from datetime import datetime, timedelta

class ChurnModel:
    """
    Segment-level churn probability estimator.
    Sprint 5: Replace placeholder constants with this.
    """
    
    def __init__(self, data_file: str = None):
        self.segment_models = {}
        self.global_base_churn = 0.05  # Default 5% baseline churn
        if data_file and os.path.exists(data_file):
            self.fit(data_file)
    
    def fit(self, data_file: str):
        """
        Fit churn probabilities per segment from historical decline outcomes.
        Expects transactions with: segment_key, churned_after_decline (bool), days_since_decline
        """
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        # Group by segment
        segment_data = {}
        for tx in data:
            seg = tx.get('segment_key', 'established|domestic')
            if seg not in segment_data:
                segment_data[seg] = []
            segment_data[seg].append(tx)
        
        # Fit per segment using empirical churn rate
        for seg, outcomes in segment_data.items():
            churn_count = sum(1 for tx in outcomes if tx.get('churned_after_decline', False))
            total = len(outcomes)
            if total > 10:
                # Empirical rate with Laplace smoothing for segments with few samples
                p_churn = (churn_count + 1) / (total + 2)
            else:
                # Fall back to global base
                p_churn = self.global_base_churn
            
            # Estimate CLV: placeholder, will be replaced with actual LTV model
            avg_transaction_value = sum(tx.get('amount', 100) for tx in outcomes) / max(1, total)
            avg_monthly_transactions = 2.0  # Placeholder
            avg_customer_lifetime_months = 36.0  # Placeholder
            
            self.segment_models[seg] = {
                'p_churn': p_churn,
                'clv': avg_transaction_value * avg_monthly_transactions * avg_customer_lifetime_months,
                'sample_count': total
            }
        
        # Global fallback for unseen segments
        global_churn = sum(m['p_churn'] for m in self.segment_models.values()) / max(1, len(self.segment_models))
        global_clv = sum(m['clv'] for m in self.segment_models.values()) / max(1, len(self.segment_models))
        self.segment_models['__global__'] = {
            'p_churn': global_churn,
            'clv': global_clv,
            'sample_count': 0
        }
    
    def predict_churn(self, segment_key: str) -> float:
        """Return P(customer_churns | declined) for segment."""
        model = self.segment_models.get(segment_key)
        if model:
            return model['p_churn']
        # Fallback to global
        return self.segment_models.get('__global__', {'p_churn': 0.05})['p_churn']
    
    def predict_clv(self, segment_key: str) -> float:
        """Return estimated customer lifetime value for segment."""
        model = self.segment_models.get(segment_key)
        if model:
            return model['clv']
        return self.segment_models.get('__global__', {'clv': 5000.0})['clv']
    
    def get_segment_stats(self) -> Dict:
        """Return all segment model stats for monitoring."""
        return self.segment_models.copy()


class RealCostModel:
    """
    Sprint 5: Cost model using real churn/CLV estimates instead of placeholder constants.
    """
    
    def __init__(self, churn_model: ChurnModel):
        self.churn_model = churn_model
        self.base_fn_cost = 100.0  # Transaction amount + fees placeholder
        self.base_fp_cost = 50.0   # Immediate lost margin placeholder
    
    def cost_of_approve(self, segment: str, is_fraud: bool, amount: float = 100.0) -> float:
        if is_fraud:
            return amount + self.base_fn_cost  # Fraud loss + fees
        return 0.0
    
    def cost_of_decline(self, segment: str, is_fraud: bool, is_false_decline: bool, amount: float = 100.0) -> float:
        if is_fraud:
            return 0.0  # Correctly blocked fraud
        if is_false_decline:
            p_churn = self.churn_model.predict_churn(segment)
            clv = self.churn_model.predict_clv(segment)
            fp_cost = self.base_fp_cost + p_churn * clv
            return fp_cost
        return 0.0
    
    def cost_of_challenge(self, segment: str, is_fraud: bool, is_false_decline: bool, amount: float = 100.0) -> float:
        if is_fraud:
            return (amount + self.base_fn_cost) * 0.5  # Might catch some
        if is_false_decline:
            p_churn = self.churn_model.predict_churn(segment) * 0.3  # Challenge less severe
            clv = self.churn_model.predict_clv(segment)
            return self.base_fp_cost * 0.3 + p_churn * clv * 0.5
        return 10.0  # Operational challenge cost