"""
Phase 3: Full rollout.
Extends to all segments with monitoring and rollback capability.
"""

import json
import time
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import DecisionServer
from src.reliability import ThresholdTableManager
from src.threshold_optimizer import ThresholdOptimizer

class FullRollout:
    def __init__(self):
        self.server = DecisionServer()
        self.manager = ThresholdTableManager()
        self.optimizer = ThresholdOptimizer()
        self.segments = [
            "new|domestic",
            "new|cross_border",
            "established|domestic",
            "established|cross_border",
            "vip|domestic",
            "vip|cross_border"
        ]
        self.fraud_ceiling = 5000.0
        self.segment_metrics = {seg: {
            'decisions': 0,
            'fraud_loss': 0.0,
            'false_declines': 0,
            'approvals': 0,
            'challenges': 0,
            'declines': 0
        } for seg in self.segments}
        self.global_metrics = {
            'total_decisions': 0,
            'fraud_loss': 0.0,
            'false_declines': 0,
            'ceiling_breaches': 0
        }
        self.decision_log = []
        self.rollback_triggered = False
    
    def publish_optimized_table(self) -> bool:
        """Generate and publish optimized threshold table for all segments."""
        try:
            # Optimize thresholds
            table = self.optimizer.optimize_all_segments('data/sample_outcomes.json', self.fraud_ceiling / 6)
            
            # Convert list format to tuple format
            formatted_table = {}
            for seg, (t_ch, t_de) in table.items():
                formatted_table[seg] = [t_ch, t_de]
            
            # Publish with canary validation
            version = f"full-{datetime.utcnow().isoformat()}"
            success = self.manager.publish_table(
                formatted_table,
                version,
                'data/historical_transactions.json',
                self.fraud_ceiling
            )
            
            if success:
                print(f"Published optimized table version: {version}")
                print("Thresholds:")
                for seg, (t_ch, t_de) in table.items():
                    print(f"  {seg}: t_challenge={t_ch:.2f}, t_decline={t_de:.2f}")
                return True
            else:
                print("Canary validation failed - table rejected")
                return False
        except Exception as e:
            print(f"Publish failed: {e}")
            return False
    
    def generate_traffic(self, tx_count: int) -> List[Dict]:
        """Generate synthetic transaction data for full rollout testing."""
        txs = []
        tiers = ['new', 'established', 'vip']
        geos = ['domestic', 'cross_border']
        
        for i in range(tx_count):
            tier = random.choice(tiers)
            geo = random.choice(geos)
            seg = f"{tier}|{geo}"
            
            # Bias toward established|domestic (higher volume)
            if random.random() < 0.3:
                seg = "established|domestic"
            
            txs.append({
                'transaction_id': f"full_tx_{i:04d}",
                'segment_key': seg,
                'segment': {
                    'customer_tier': seg.split('|')[0],
                    'geography': seg.split('|')[1]
                },
                'combined_risk_score': random.uniform(0.05, 0.98),
                'amount': random.uniform(20.0, 1000.0),
                'is_fraud': random.random() < 0.03,
                'is_false_decline': random.random() < 0.08,
                'churned_after_decline': random.random() < 0.15,
                'ring_score': random.random() * 0.85
            })
        return txs
    
    def process_transaction(self, tx: Dict) -> Dict:
        """Process a transaction and update metrics."""
        seg_key = tx.get('segment_key', 'established|domestic')
        
        # Get decision
        result = self.server.decide({
            'combined_risk_score': tx.get('combined_risk_score', 0.5),
            'segment': tx.get('segment', {}),
            'ring_score': tx.get('ring_score', 0.0),
            'confirmed_members': 0
        })
        
        # Update metrics
        self.global_metrics['total_decisions'] += 1
        
        # Update segment metrics
        if seg_key in self.segment_metrics:
            seg_metrics = self.segment_metrics[seg_key]
            seg_metrics['decisions'] += 1
            
            if result['decision'] == 'APPROVE':
                seg_metrics['approvals'] += 1
            elif result['decision'] == 'CHALLENGE':
                seg_metrics['challenges'] += 1
            else:
                seg_metrics['declines'] += 1
            
            # Track fraud loss
            if tx.get('is_fraud', False) and result['decision'] in ['APPROVE', 'CHALLENGE']:
                loss = tx.get('amount', 100.0) * (0.5 if result['decision'] == 'CHALLENGE' else 1.0)
                seg_metrics['fraud_loss'] += loss
                self.global_metrics['fraud_loss'] += loss
            
            # Track false declines
            if tx.get('is_false_decline', False) and result['decision'] == 'DECLINE':
                seg_metrics['false_declines'] += 1
                self.global_metrics['false_declines'] += 1
        
        # Check ceiling
        if self.global_metrics['fraud_loss'] > self.fraud_ceiling:
            self.global_metrics['ceiling_breaches'] += 1
            self.rollback_triggered = True
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'transaction_id': tx.get('transaction_id'),
            'segment_key': seg_key,
            'decision': result['decision'],
            'fraud_loss': self.global_metrics['fraud_loss']
        }
        self.decision_log.append(log_entry)
        
        return result
    
    def monitor_metrics(self) -> Dict:
        """Generate current metrics report."""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_decisions': self.global_metrics['total_decisions'],
            'fraud_loss': self.global_metrics['fraud_loss'],
            'fraud_ceiling': self.fraud_ceiling,
            'ceiling_usage': self.global_metrics['fraud_loss'] / self.fraud_ceiling * 100 if self.fraud_ceiling > 0 else 0,
            'false_declines': self.global_metrics['false_declines'],
            'segments': self.segment_metrics
        }
        return report
    
    def check_rollback_condition(self) -> bool:
        """Determine if rollback is required."""
        if self.rollback_triggered:
            return True
        if self.global_metrics['fraud_loss'] > self.fraud_ceiling * 1.1:
            return True
        return False
    
    def execute_rollback(self):
        """Rollback to last known good table."""
        success = self.manager.rollback_to_lkg()
        if success:
            print("ROLLBACK EXECUTED: Reverted to last known good table")
            self.rollback_triggered = False
        return success
    
    def run_rollout(self, tx_count: int = 200, duration_minutes: int = 3):
        """Execute full rollout across all segments."""
        print("=== FULL ROLLOUT ===")
        print(f"Segments: {', '.join(self.segments)}")
        print(f"Fraud ceiling: {self.fraud_ceiling}")
        print(f"Transactions: {tx_count}")
        print("---")
        
        # Publish optimized table
        if not self.publish_optimized_table():
            print("Cannot proceed: table publish failed")
            return False
        
        print("\nGenerating traffic...")
        txs = self.generate_traffic(tx_count)
        print(f"Processing {len(txs)} transactions...")
        
        # Process transactions with rate limiting
        start_time = datetime.now()
        for i, tx in enumerate(txs):
            self.process_transaction(tx)
            
            # Progress update
            if (i + 1) % 25 == 0:
                elapsed = (datetime.now() - start_time).seconds
                print(f"  Processed {i+1}/{len(txs)} | "
                      f"Fraud loss: {self.global_metrics['fraud_loss']:.2f}/{self.fraud_ceiling} | "
                      f"False declines: {self.global_metrics['false_declines']}")
            
            # Check rollback condition periodically
            if self.check_rollback_condition():
                print("\nRollback condition detected!")
                self.execute_rollback()
                break
            
            # Simulate real-time delay
            time.sleep(random.uniform(0.05, 0.2))
        
        # Final report
        self._print_final_report()
        
        # Save log
        log_file = f"full_rollout_log_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump({
                'metrics': self.global_metrics,
                'segment_metrics': self.segment_metrics,
                'decisions': self.decision_log[-200:]
            }, f, indent=2)
        print(f"Log saved to {log_file}")
        
        return not self.rollback_triggered
    
    def _print_final_report(self):
        """Print final rollout report."""
        print("\n=== FULL ROLLOUT FINAL REPORT ===")
        print(f"Total decisions: {self.global_metrics['total_decisions']}")
        print(f"Fraud loss: {self.global_metrics['fraud_loss']:.2f} / {self.fraud_ceiling} (ceiling)")
        print(f"Ceiling usage: {self.global_metrics['fraud_loss']/self.fraud_ceiling*100:.1f}%")
        print(f"False declines: {self.global_metrics['false_declines']}")
        print(f"Ceiling breaches: {self.global_metrics['ceiling_breaches']}")
        print(f"Rollback triggered: {self.rollback_triggered}")
        
        print("\nSegment breakdown:")
        for seg, metrics in self.segment_metrics.items():
            if metrics['decisions'] > 0:
                print(f"  {seg}:")
                print(f"    Decisions: {metrics['decisions']}")
                print(f"    APPROVE: {metrics['approvals']}, CHALLENGE: {metrics['challenges']}, DECLINE: {metrics['declines']}")
                print(f"    Fraud loss: {metrics['fraud_loss']:.2f}")
                print(f"    False declines: {metrics['false_declines']}")
        
        if not self.rollback_triggered and self.global_metrics['fraud_loss'] <= self.fraud_ceiling:
            print("\nROLLOUT SUCCESSFUL: All segments live with optimized thresholds")
        else:
            print("\nROLLOUT FAILED: Rollback executed")

if __name__ == '__main__':
    rollout = FullRollout()
    rollout.run_rollout(tx_count=150, duration_minutes=2)