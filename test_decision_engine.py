
"""
Unit test for decision engine.
"""

from src.decision_engine import DecisionEngine

def test_ring_override():
    engine = DecisionEngine()
    
    # Override case
    result = engine.decide(0.50, {"customer_tier": "new", "geography": "domestic"}, ring_score=0.95, confirmed_members=3)
    assert result["decision"] == "DECLINE"
    assert result["override"] == True
    
    # No override
    result = engine.decide(0.50, {"customer_tier": "new", "geography": "domestic"}, ring_score=0.80, confirmed_members=1)
    assert result["override"] == False
    
    print("Ring override test passed.")

def test_segment_lookup():
    engine = DecisionEngine()
    
    # Known segment
    result = engine.decide(0.30, {"customer_tier": "new", "geography": "domestic"})
    assert result["segment_matched"] == "new|domestic"
    assert result["t_challenge"] == 0.40
    
    # Unknown segment falls back
    result = engine.decide(0.30, {"customer_tier": "unknown", "geography": "mars"})
    assert result["segment_matched"] == "unknown|domestic"
    
    print("Segment lookup test passed.")

def test_decision_logic():
    engine = DecisionEngine()
    
    # APPROVE
    result = engine.decide(0.20, {"customer_tier": "established", "geography": "domestic"})
    assert result["decision"] == "APPROVE"
    
    # CHALLENGE
    result = engine.decide(0.70, {"customer_tier": "established", "geography": "domestic"})
    assert result["decision"] == "CHALLENGE"
    
    # DECLINE
    result = engine.decide(0.95, {"customer_tier": "established", "geography": "domestic"})
    assert result["decision"] == "DECLINE"
    
    print("Decision logic test passed.")

if __name__ == "__main__":
    test_ring_override()
    test_segment_lookup()
    test_decision_logic()
    print("All tests passed.")