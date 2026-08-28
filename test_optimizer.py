from src.threshold_optimizer import ThresholdOptimizer

optimizer = ThresholdOptimizer()
table = optimizer.optimize_all_segments('data/sample_outcomes.json', fraud_ceiling=500.0)
print("Optimized threshold table:")
for seg, thresholds in table.items():
    print(f"  {seg}: {thresholds}")