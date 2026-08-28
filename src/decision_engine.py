"""
Sprint 3: Decision engine integration.
Accepts risk_score + segment, returns APPROVE/CHALLENGE/DECLINE.
"""

from typing import Dict, Tuple
import json
import os

# Threshold table structure: segment_key -> (t_challenge, t_decline)
# Sprint 2 placeholder: coarse segments with fixed thresholds
THRESHOLD_TABLE = {
    "new|domestic": (0.40, 0.85),
    "new|cross_border": (0.30, 0.75),
    "established|domestic": (0.55, 0.90),
    "established|cross_border": (0.45, 0.85),
    "vip|domestic": (0.65, 0.95),
    "vip|cross_border": (0.55, 0.90),
}

class DecisionEngine:
    def __init__(self, threshold_table: Dict[str, Tuple[float, float]] = None):
        self.threshold_table = threshold_table or THRESHOLD_TABLE
        self.version = "2026-08-28T00:00Z-v1"
    
    def _ring_override(self, ring_score: float, confirmed_members: int) -> str:
        """Hard override from graph system. Takes precedence."""
        if ring_score > 0.90 and confirmed_members >= 2:
            return "DECLINE"
        return None
    
    def _segment_key(self, segment: Dict) -> str:
        """Build segment key from segment features."""
        tier = segment.get("customer_tier", "established")
        geo = segment.get("geography", "domestic")
        return f"{tier}|{geo}"
    
    def decide(self, combined_risk_score: float, segment: Dict, ring_score: float = 0.0, confirmed_members: int = 0) -> Dict:
        """
        Returns decision with audit trail.
        """
        # Step 1: Ring override
        override = self._ring_override(ring_score, confirmed_members)
        if override:
            return {
                "decision": override,
                "threshold_table_version": self.version,
                "segment_matched": None,
                "t_challenge": None,
                "t_decline": None,
                "override": True
            }
        
        # Step 2: Segment lookup
        seg_key = self._segment_key(segment)
        threshold = self.threshold_table.get(seg_key)
        if not threshold:
            # Fallback: coarser segment
            tier = segment.get("customer_tier", "established")
            seg_key = f"{tier}|domestic"
            threshold = self.threshold_table.get(seg_key, (0.50, 0.88))
        
        t_challenge, t_decline = threshold
        
        # Step 3: Decision
        if combined_risk_score < t_challenge:
            decision = "APPROVE"
        elif combined_risk_score < t_decline:
            decision = "CHALLENGE"
        else:
            decision = "DECLINE"
        
        return {
            "decision": decision,
            "threshold_table_version": self.version,
            "segment_matched": seg_key,
            "t_challenge": t_challenge,
            "t_decline": t_decline,
            "override": False
        }