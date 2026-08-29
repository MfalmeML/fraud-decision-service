from src.churn_model import ChurnModel, RealCostModel

# Fit churn model
churn_model = ChurnModel()
churn_model.fit('data/decline_outcomes.json')

print("Segment models:")
for seg, stats in churn_model.get_segment_stats().items():
    if seg != '__global__':
        print(f"  {seg}: p_churn={stats['p_churn']:.3f}, clv={stats['clv']:.2f}, n={stats['sample_count']}")

print(f"\nGlobal fallback: p_churn={churn_model.predict_churn('__global__'):.3f}")

# Test predictions
print("\nPredictions:")
test_segments = ['new|domestic', 'established|domestic', 'vip|domestic', 'unknown']
for seg in test_segments:
    print(f"  {seg}: p_churn={churn_model.predict_churn(seg):.3f}, clv={churn_model.predict_clv(seg):.2f}")

# Real cost model
cost_model = RealCostModel(churn_model)

# Compare cost of declining a legitimate VIP vs new customer
print("\nCost of false decline:")
for seg in ['vip|domestic', 'new|domestic']:
    cost = cost_model.cost_of_decline(seg, is_fraud=False, is_false_decline=True, amount=100.0)
    print(f"  {seg}: {cost:.2f}")

print("\nTest complete.")