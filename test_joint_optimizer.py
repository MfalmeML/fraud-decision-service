from src.joint_optimizer import JointOptimizer

optimizer = JointOptimizer()

# Optimize with total fraud ceiling of 2000
table = optimizer.optimize('data/sample_outcomes.json', total_fraud_ceiling=500.0)

print("Joint optimized threshold table:")
for seg, (t_ch, t_de) in table.items():
    print(f"  {seg}: t_challenge={t_ch:.2f}, t_decline={t_de:.2f}")

# Compare with independent grid search
from src.threshold_optimizer import ThresholdOptimizer
independent = ThresholdOptimizer()
ind_table = independent.optimize_all_segments('data/sample_outcomes.json', fraud_ceiling=500.0)

print("\nIndependent grid search (per-segment) for comparison:")
for seg, (t_ch, t_de) in ind_table.items():
    print(f"  {seg}: t_challenge={t_ch:.2f}, t_decline={t_de:.2f}")

print("\nJoint optimizer complete.")