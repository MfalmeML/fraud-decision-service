"""
Phase 1: Shadow mode runner.
Runs decision engine in parallel with existing fixed threshold.
Compares decisions and simulates business impact.
"""

import json
import csv
from datetime import datetime
from typing import Dict, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decision_engine import DecisionEngine
from src.reliability import ThresholdTableManager
from src.churn_model import ChurnModel, RealCostModel

class ShadowRunner:
    def __init__(self):
        self.engine = DecisionEngine()
        self.manager = ThresholdTableManager()
        self.churn_model = ChurnModel()
        self.cost_model = None
        self.fixed_threshold = 0.50  # Current production threshold
        
    def load_transactions(self, filepath: str) -> List[Dict]:
        """Load historical transaction data with known outcomes."""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def simulate_decision(self, tx: Dict) -> Dict:
        """Run both fixed threshold and cost-sensitive decision."""
        score = tx.get('combined_risk_score', 0.5)
        segment = tx.get('segment', {'customer_tier': 'established', 'geography': 'domestic'})
        ring_score = tx.get('ring_score', 0.0)
        confirmed = tx.get('confirmed_members', 0)
        
        # Fixed threshold decision
        fixed_decision = 'APPROVE' if score < self.fixed_threshold else 'DECLINE'
        
        # Cost-sensitive decision
        seg_key = f"{segment.get('customer_tier', 'established')}|{segment.get('geography', 'domestic')}"
        t_ch, t_de = self.manager.lookup(seg_key)
        
        if score < t_ch:
            cs_decision = 'APPROVE'
        elif score < t_de:
            cs_decision = 'CHALLENGE'
        else:
            cs_decision = 'DECLINE'
        
        return {
            'transaction_id': tx.get('transaction_id'),
            'score': score,
            'segment_key': seg_key,
            'fixed_decision': fixed_decision,
            'cs_decision': cs_decision,
            't_challenge': t_ch,
            't_decline': t_de,
            'is_fraud': tx.get('is_fraud', False),
            'is_false_decline': tx.get('is_false_decline', False),
            'churned': tx.get('churned_after_decline', False),
            'amount': tx.get('amount', 100.0),
            'differs': fixed_decision != cs_decision
        }
    
    def compute_impact(self, results: List[Dict]) -> Dict:
        """Compute business impact vs fixed threshold baseline."""
        fixed_fraud_loss = 0.0
        cs_fraud_loss = 0.0
        fixed_fp_cost = 0.0
        cs_fp_cost = 0.0
        fixed_challenge_cost = 0.0
        cs_challenge_cost = 0.0
        
        # Load or create cost model with churn estimates
        if os.path.exists('data/decline_outcomes.json'):
            self.churn_model.fit('data/decline_outcomes.json')
        self.cost_model = RealCostModel(self.churn_model)
        
        for r in results:
            amount = r['amount']
            seg = r['segment_key']
            is_fraud = r['is_fraud']
            is_false_decline = r['is_false_decline']
            churned = r['churned']
            
            # Fixed threshold costs
            if r['fixed_decision'] == 'APPROVE':
                if is_fraud:
                    fixed_fraud_loss += amount + 100.0
            elif r['fixed_decision'] == 'DECLINE':
                if is_false_decline:
                    fixed_fp_cost += self.cost_model.cost_of_decline(seg, False, True, amount)
            elif r['fixed_decision'] == 'CHALLENGE':
                fixed_challenge_cost += 10.0
                if is_false_decline:
                    fixed_fp_cost += self.cost_model.cost_of_challenge(seg, False, True, amount) * 0.5
            
            # Cost-sensitive costs
            if r['cs_decision'] == 'APPROVE':
                if is_fraud:
                    cs_fraud_loss += amount + 100.0
            elif r['cs_decision'] == 'DECLINE':
                if is_false_decline:
                    cs_fp_cost += self.cost_model.cost_of_decline(seg, False, True, amount)
            elif r['cs_decision'] == 'CHALLENGE':
                cs_challenge_cost += 10.0
                if is_false_decline:
                    cs_fp_cost += self.cost_model.cost_of_challenge(seg, False, True, amount) * 0.5
        
        total_fixed_cost = fixed_fraud_loss + fixed_fp_cost + fixed_challenge_cost
        total_cs_cost = cs_fraud_loss + cs_fp_cost + cs_challenge_cost
        net_benefit = total_fixed_cost - total_cs_cost
        
        return {
            'fixed_fraud_loss': fixed_fraud_loss,
            'cs_fraud_loss': cs_fraud_loss,
            'fixed_fp_cost': fixed_fp_cost,
            'cs_fp_cost': cs_fp_cost,
            'fixed_challenge_cost': fixed_challenge_cost,
            'cs_challenge_cost': cs_challenge_cost,
            'total_fixed_cost': total_fixed_cost,
            'total_cs_cost': total_cs_cost,
            'net_benefit': net_net_benefit,
            'decision_difference_rate': sum(1 for r in results if r['differs']) / len(results) if results else 0
        }
    
    def run_shadow(self, input_file: str, output_file: str = 'shadow_results.json'):
        """Run shadow mode on historical transactions."""
        print(f"Loading transactions from {input_file}")
        txs = self.load_transactions(input_file)
        print(f"Processing {len(txs)} transactions")
        
        results = []
        for tx in txs:
            results.append(self.simulate_decision(tx))
        
        # Save detailed results
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Compute impact
        impact = self.compute_impact(results)
        
        print("\n=== Shadow Mode Results ===")
        print(f"Transactions processed: {len(results)}")
        print(f"Decisions differ: {impact['decision_difference_rate']*100:.1f}%")
        print(f"\nFixed threshold costs:")
        print(f"  Fraud loss: {impact['fixed_fraud_loss']:.2f}")
        print(f"  False decline cost: {impact['fixed_fp_cost']:.2f}")
        print(f"  Challenge cost: {impact['fixed_challenge_cost']:.2f}")
        print(f"  Total: {impact['total_fixed_cost']:.2f}")
        print(f"\nCost-sensitive costs:")
        print(f"  Fraud loss: {impact['cs_fraud_loss']:.2f}")
        print(f"  False decline cost: {impact['cs_fp_cost']:.2f}")
        print(f"  Challenge cost: {impact['cs_challenge_cost']:.2f}")
        print(f"  Total: {impact['total_cs_cost']:.2f}")
        print(f"\nNet benefit vs fixed threshold: {impact['net_benefit']:.2f}")
        
        return results, impact

if __name__ == '__main__':
    runner = ShadowRunner()
    
    # Create sample historical data if none exists
    if not os.path.exists('data/historical_transactions.json'):
        sample_data = [
            {"transaction_id": "tx001", "combined_risk_score": 0.45, "segment": {"customer_tier": "established", "geography": "domestic"}, "is_fraud": False, "is_false_decline": False, "churned_after_decline": False, "amount": 150.0},
            {"transaction_id": "tx002", "combined_risk_score": 0.75, "segment": {"customer_tier": "new", "geography": "cross_border"}, "is_fraud": True, "is_false_decline": False, "churned_after_decline": False, "amount": 300.0},
            {"transaction_id": "tx003", "combined_risk_score": 0.55, "segment": {"customer_tier": "established", "geography": "domestic"}, "is_fraud": False, "is_false_decline": True, "churned_after_decline": True, "amount": 200.0},
            {"transaction_id": "tx004", "combined_risk_score": 0.35, "segment": {"customer_tier": "vip", "geography": "domestic"}, "is_fraud": False, "is_false_decline": False, "churned_after_decline": False, "amount": 500.0},
            {"transaction_id": "tx005", "combined_risk_score": 0.85, "segment": {"customer_tier": "new", "geography": "domestic"}, "is_fraud": True, "is_false_decline": False, "churned_after_decline": False, "amount": 100.0},
            {"transaction_id": "tx006", "combined_risk_score": 0.60, "segment": {"customer_tier": "established", "geography": "cross_border"}, "is_fraud": False, "is_false_decline": True, "churned_after_decline": False, "amount": 250.0},
            {"transaction_id": "tx007", "combined_risk_score": 0.48, "segment": {"customer_tier": "vip", "geography": "cross_border"}, "is_fraud": False, "is_false_decline": False, "churned_after_decline": False, "amount": 1000.0},
            {"transaction_id": "tx008", "combined_risk_score": 0.92, "segment": {"customer_tier": "new", "geography": "domestic"}, "is_fraud": False, "is_false_decline": True, "churned_after_decline": True, "amount": 80.0},
            {"transaction_id": "tx009", "combined_risk_score": 0.25, "segment": {"customer_tier": "established", "geography": "domestic"}, "is_fraud": False, "is_false_decline": False, "churned_after_decline": False, "amount": 60.0},
            {"transaction_id": "tx010", "combined_risk_score": 0.78, "segment": {"customer_tier": "new", "geography": "cross_border"}, "is_fraud": True, "is_false_decline": False, "churned_after_decline": False, "amount": 450.0}
        ]
        with open('data/historical_transactions.json', 'w') as f:
            json.dump(sample_data, f, indent=2)
    
    runner.run_shadow('data/historical_transactions.json')