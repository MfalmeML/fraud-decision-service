from src.reliability import ThresholdTableManager

# Test 1: Initialization
mgr = ThresholdTableManager()
print(f"Initial version: {mgr.get_version()}")
print(f"Lookup established|domestic: {mgr.lookup('established|domestic')}")
print(f"Lookup missing segment (fallback): {mgr.lookup('unknown|mars')}")

# Test 2: Publish new table
new_table = {
    "new|domestic": [0.50, 0.90],
    "established|domestic": [0.60, 0.92],
}
success = mgr.publish_table(new_table, "2026-08-28T12:00Z-v2", "data/sample_outcomes.json", fraud_ceiling=1000.0)
print(f"Publish success: {success}")
print(f"New version: {mgr.get_version()}")
print(f"Updated lookup: {mgr.lookup('established|domestic')}")

# Test 3: Rollback
mgr.rollback_to_lkg()
print(f"After rollback version: {mgr.get_version()}")
print(f"Rollback lookup: {mgr.lookup('established|domestic')}")

# Test 4: Stale check
print(f"Stale? {mgr.is_stale()}")

print("Reliability tests complete.")