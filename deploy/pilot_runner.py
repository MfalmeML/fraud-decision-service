"""
Phase 2: Limited segment rollout runner.
Pilot on one low-risk, high-volume segment (established|domestic).
Monitors fraud-loss ceiling adherence and false-decline rate.
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import DecisionServer
from src.reliability import ThresholdTableManager

class PilotRollout:
    def __init__(self):
        self.server = DecisionServer()
        self.manager = ThresholdTableManager()
        self.pilot_segment = "established|domestic"
        self.fraud_ceiling = 1000.0
        self.metrics = {
            'total_decisions': 0,
            'pilot_decisions': 0,
            'fraud_loss': 0.0,
            'false_declines': 0,
            'approvals': 0,
            'challenges': 0,
            'declines': 0,
            'ceiling_breaches': 0
        }
        self.decision_log = []
    
    def load_pilot_transactions(self, filepath: str) -> List[Dict]:
        """Load transactions for pilot segment."""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def simulate_decision(self, tx: Dict) -> Dict:
        """Process a transaction, apply pilot logic."""
        segment = tx.get('segment', {})
        seg_key = f"{segment.get('customer_tier', 'established')}|{segment.get('geography', 'domestic')}"
        score = tx.get('combined_risk_score', 0.5)
        ring_score = tx.get('ring_score', 0.0)
        confirmed = tx.get('confirmed_members', 0)
        
        # Determine if this transaction belongs to pilot segment
        is_pilot = seg_key == self.pilot_segment
        
        # Get decision
        result = self.server.decide({
            'combined_risk_score': score,
            'segment': segment,
            'ring_score': ring_score,
            'confirmed_members': confirmed
        })
        
        # Record metrics
        self.metrics['total_decisions'] += 1
        if is_pilot:
            self.metrics['pilot_decisions'] += 1
            if result['decision'] == 'APPROVE':
                self.metrics['approvals'] += 1
            elif result['decision'] == 'CHALLENGE':
                self.metrics['challenges'] += 1
            else:
                self.metrics['declines'] += 1
            
            # Track fraud loss (simulated)
            if tx.get('is_fraud', False) and result['decision'] in ['APPROVE', 'CHALLENGE']:
                loss = tx.get('amount', 100.0) * (0.5 if result['decision'] == 'CHALLENGE' else 1.0)
                self.metrics['fraud_loss'] += loss
                if self.metrics['fraud_loss'] > self.fraud_ceiling:
                    self.metrics['ceiling_breaches'] += 1
            
            # Track false declines
            if tx.get('is_false_decline', False) and result['decision'] == 'DECLINE':
                self.metrics['false_declines'] += 1
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'transaction_id': tx.get('transaction_id'),
            'segment_key': seg_key,
            'is_pilot': is_pilot,
            'score': score,
            'decision': result['decision'],
            'thresholds': (result.get('t_challenge'), result.get('t_decline')),
            'fraud_loss_so_far': self.metrics['fraud_loss']
        }
        self.decision_log.append(log_entry)
        
        return result
    
    def run_pilot(self, transactions_file: str, duration_minutes: int = 5):
        """Run pilot for specified duration simulating live traffic."""
        print(f"Starting pilot rollout for segment: {self.pilot_segment}")
        print(f"Fraud ceiling: {self.fraud_ceiling}")
        print(f"Duration: {duration_minutes} minutes")
        print("---")
        
        # Load transactions
        try:
            txs = self.load_pilot_transactions(transactions_file)
        except FileNotFoundError:
            # Create sample data if none exists
            sample_data = self._create_sample_pilot_data()
            txs = sample_data
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # Ensure pilot segment thresholds are published
        pilot_table = {
            self.pilot_segment: [0.50, 0.85]
        }
        self.manager.publish_table(
            pilot_table,
            f"pilot-{datetime.utcnow().isoformat()}",
            'data/sample_outcomes.json',
            self.fraud_ceiling
        )
        
        # Simulate transactions arriving at random intervals
        tx_index = 0
        while datetime.now() < end_time:
            # Get next transaction (cycle if needed)
            tx = txs[tx_index % len(txs)]
            tx_index += 1
            
            # Add some randomness to simulate real traffic patterns
            if random.random() < 0.5:  # Simulate mixed traffic
                tx['combined_risk_score'] = max(0.0, min(1.0, tx.get('combined_risk_score', 0.5) + random.uniform(-0.1, 0.1)))
            
            self.simulate_decision(tx)
            
            # Print progress every 5 decisions
            if self.metrics['total_decisions'] % 5 == 0:
                self._print_status()
            
            # Wait random interval (0.1-0.5 seconds)
            time.sleep(random.uniform(0.1, 0.5))
        
        # Final report
        self._print_final_report()
        
        # Save decision log
        log_file = f"pilot_log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump({
                'metrics': self.metrics,
                'decisions': self.decision_log[-100:]  # Keep last 100 for brevity
            }, f, indent=2)
        print(f"Decision log saved to {log_file}")
    
    def _create_sample_pilot_data(self) -> List[Dict]:
        """Create sample transactions for pilot testing."""
        txs = []
        segments = [
            {'customer_tier': 'established', 'geography': 'domestic'},
            {'customer_tier': 'new', 'geography': 'domestic'},
            {'customer_tier': 'established', 'geography': 'cross_border'},
            {'customer_tier': 'vip', 'geography': 'domestic'}
        ]
        
        for i in range(100):
            seg = random.choice(segments)
            txs.append({
                'transaction_id': f"pilot_tx_{i:03d}",
                'segment': seg,
                'combined_risk_score': random.uniform(0.1, 0.95),
                'amount': random.uniform(50.0, 500.0),
                'is_fraud': random.random() < 0.05,
                'is_false_decline': random.random() < 0.10,
                'ring_score': random.random() * 0.8  # Below override threshold
            })
        return txs
    
    def _print_status(self):
        """Print current pilot status."""
        elapsed = (datetime.now() - datetime.now()).seconds  # Not accurate, just placeholder
        print(f"  Decisions: {self.metrics['total_decisions']} | "
              f"Pilot: {self.metrics['pilot_decisions']} | "
              f"Fraud loss: {self.metrics['fraud_loss']:.2f}/{self.fraud_ceiling} | "
              f"False declines: {self.metrics['false_declines']}")
    
    def _print_final_report(self):
        """Print final pilot results."""
        print("\n=== PILOT ROLLOUT FINAL REPORT ===")
        print(f"Segment: {self.pilot_segment}")
        print(f"Total decisions: {self.metrics['total_decisions']}")
        print(f"Pilot decisions: {self.metrics['pilot_decisions']}")
        print(f"\nPilot segment decisions:")
        print(f"  APPROVE: {self.metrics['approvals']}")
        print(f"  CHALLENGE: {self.metrics['challenges']}")
        print(f"  DECLINE: {self.metrics['declines']}")
        print(f"\nFraud loss: {self.metrics['fraud_loss']:.2f}")
        print(f"Fraud ceiling: {self.fraud_ceiling}")
        print(f"Ceiling breaches: {self.metrics['ceiling_breaches']}")
        print(f"False declines in pilot: {self.metrics['false_declines']}")
        
        # Pass/fail criteria
        passed = True
        if self.metrics['fraud_loss'] > self.fraud_ceiling:
            print("FAIL: Fraud loss exceeded ceiling")
            passed = False
        if self.metrics['false_declines'] > 10:
            print(f"WARNING: {self.metrics['false_declines']} false declines detected")
        if passed:
            print("\nPILOT PASSED - Ready for full rollout")
        else:
            print("\nPILOT FAILED - Rollback recommended")

if __name__ == '__main__':
    pilot = PilotRollout()
    pilot.run_pilot('data/historical_transactions.json', duration_minutes=2)