# Fraud Decision Service

**A production-grade, cost-sensitive decisioning layer that replaces fixed fraud thresholds with segment-aware, profit-optimized decisions.**

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-92%25-brightgreen)]()
[![Latency](https://img.shields.io/badge/latency-%3C2ms-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.8+-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

---

## Table of Contents

- [The Problem This Solves](#the-problem-this-solves)
- [Architecture](#architecture)
- [Decision Flow](#decision-flow)
- [Key Capabilities](#key-capabilities)
- [Build Sequence](#build-sequence)
- [Deployment Phases](#deployment-phases)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Monitoring](#monitoring)
- [Business Impact Equation](#business-impact-equation)
- [Testing](#testing)
- [Requirements](#requirements)
- [Contributing](#contributing)

---

## The Problem This Solves

Most fraud systems optimize for **accuracy** — but accuracy treats every error as equally costly. It isn't.

| Error Type | What Actually Happens | Typical Cost |
|---|---|---|
| **False Negative** (fraud approved) | Direct fraud loss, chargebacks, network penalties | High, but bounded to the transaction amount |
| **False Positive** (legitimate transaction declined) | Customer friction, cart abandonment, churn | Often **higher** — one declined customer may stop transacting entirely |

A single global threshold silently assumes every customer and every transaction has the same cost structure. They don't. A VIP customer with three years of clean history and a KES 500 purchase has a completely different false-positive cost than a brand-new account attempting a KES 180,000 cross-border transaction.

This service replaces that placeholder with an explicit, tunable, auditable decision layer that asks one question:

> *"Given this risk score, and given what it costs to be wrong in either direction, what's the optimal action?"*

---

## Architecture

![System architecture diagram showing tabular and graph models feeding a fusion layer into segment lookup, cost model and threshold table, decision engine, and approve/challenge/decline outcomes with a feedback loop](images/architecture.png)

The service sits **downstream** of your existing risk models — it does not replace them. The tabular model's `fraud_probability` and the graph model's `ring_score` are fused upstream into a single `combined_risk_score`; this service decides what to *do* with that score, using a segment-specific, cost-optimized threshold table rather than one global cutoff. Confirmed outcomes flow back into the cost model, closing the loop.

---

## Decision Flow

![Decision flow diagram showing risk score, segment, and graph signal feeding a ring override check, then segment lookup against the threshold table, threshold comparison, and approve, challenge, or decline outcomes](images/flow.png)

Every request passes through a **hard override check** first: an account tied to a confirmed fraud ring (`ring_score > 0.90` with ≥ 2 confirmed members) is force-declined regardless of the cost-sensitive logic below it. Everything else is resolved by comparing `combined_risk_score` against that segment's `(t_challenge, t_decline)` pair, read from an in-memory, versioned threshold table.

---

## Key Capabilities

### 1. Segment-Aware Thresholds

Instead of one global threshold, each segment gets its own optimized pair:

| Segment | t_challenge | t_decline |
|---|---|---|
| new \| domestic | 0.40 | 0.85 |
| new \| cross_border | 0.30 | 0.75 |
| established \| domestic | 0.55 | 0.90 |
| established \| cross_border | 0.45 | 0.85 |
| vip \| domestic | 0.65 | 0.95 |
| vip \| cross_border | 0.55 | 0.90 |

### 2. Cost Model

Before any optimization, the system builds explicit cost estimates — not intuition:

```
FN_cost = transaction_amount + chargeback_fee + network_penalty_risk
FP_cost = lost_margin + P(churn | decline) × CLV + support_cost
CH_cost = P(abandonment | challenge) × margin + operational_cost
```

`P(churn | decline)` and `CLV` come from real survival/churn models fit per segment — not global constants. Get these right and the optimizer makes money. Get them wrong and the system *looks* scientific while quietly destroying value.

### 3. Optimization Engine

| Method | Description | When to Use |
|---|---|---|
| **Grid Search** | Sweep thresholds per segment, pick the best under the fraud-loss ceiling | Ship first — auditable, simple, works today |
| **Joint Optimizer** | Reallocates fraud-loss budget across segments jointly | After validation — e.g. VIP friction is more expensive than fraud in new accounts |

### 4. Reliability Layer

| Failure | Fallback |
|---|---|
| Threshold table stale or unreachable | Last-known-good table |
| Segment has insufficient outcome data | Parent / coarser segment threshold |
| Churn or CLV model degrades | Freeze thresholds, alert — never silently keep optimizing on bad inputs |
| Candidate table fails backtest | Reject, keep serving the previous version |

### 5. Decision Latency

| Path | Budget | Contents |
|---|---|---|
| Authorization-time (hot) | **~2 ms** | Segment key lookup + threshold read + comparison |
| Threshold refresh (warm) | Minutes | Aggregate outcomes, recompute cost-model inputs |
| Full re-optimization (cold) | Daily–weekly | Full grid search, canary-validate, publish |

All expensive work happens offline — this service adds negligible latency to the authorization path.

---

## Build Sequence

```
┌────────────────────────────────────────────────────────────────┐
│ Sprint 1 · Outcome Feedback Pipeline                            │
│   Capture is_false_decline and churned_after_decline signals    │
├────────────────────────────────────────────────────────────────┤
│ Sprint 2 · Coarse Cost Model + Grid Search                      │
│   Placeholder costs → grid search → first threshold table       │
├────────────────────────────────────────────────────────────────┤
│ Sprint 3 · Decision Engine Integration                          │
│   Replace fixed threshold with segment-aware lookup             │
├────────────────────────────────────────────────────────────────┤
│ Sprint 4 · Reliability Layer                                    │
│   Fallback logic, table versioning, canary gate                 │
├────────────────────────────────────────────────────────────────┤
│ Sprint 5 · Real Cost-Model Inputs                                │
│   Fit churn/CLV models → replace placeholder constants          │
├────────────────────────────────────────────────────────────────┤
│ Sprint 6 · Joint Optimizer                                      │
│   Reallocate fraud-loss budget across segments                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Deployment Phases

```
Phase 1 · Shadow Mode
  Run parallel with the existing fixed threshold for 2–4 weeks, no live impact

Phase 2 · Pilot Segment
  Cut over one low-risk, high-volume segment first; monitor daily

Phase 3 · Full Rollout
  Extend to all segments, with monitoring and instant rollback
```

Rollback is a pointer swap to the previous threshold table version — not a code deploy.

---

## Quick Start

```bash
# Clone and navigate
git clone <repository>
cd fraud-decision-service

# Install dependencies
pip install -r requirements.txt

# Run tests
python run_all_tests.py

# Audit system
python audit_system.py

# Start production
deploy/start_production.sh    # Linux/Mac
deploy\start_production.bat   # Windows
```

---

## API Reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/decide` | Make a decision |
| `POST` | `/outcome` | Record a confirmed outcome |
| `POST` | `/publish` | Publish a new threshold table |
| `GET` | `/health` | Health check |
| `GET` | `/thresholds/{segment}` | Get current thresholds for a segment |
| `GET` | `/outcome?transaction_id=&label=` | Retrieve a recorded outcome |

### Decision Request

```json
POST /decide
{
  "combined_risk_score": 0.63,
  "segment": {
    "customer_tier": "established",
    "channel": "app",
    "geography": "cross_border"
  },
  "ring_score": 0.0,
  "confirmed_members": 0
}
```

### Decision Response

```json
{
  "decision": "CHALLENGE",
  "threshold_table_version": "2026-08-30T00:00Z-v14",
  "segment_matched": "established|app|electronics|cross_border",
  "t_challenge": 0.50,
  "t_decline": 0.88,
  "override": false
}
```

---

## Monitoring

![Risk ops dashboard mockup showing a fraud loss ceiling gauge, decision mix over seven days, net benefit KPI, segment threshold table, and decision audit trace panel](images/dashboard.png)

The risk ops dashboard surfaces everything a reviewer needs without touching a database directly:

- **Fraud-loss ceiling usage** — how much of the current cycle's budget has been spent
- **Decision mix** — approve / challenge / decline rates over time, by segment
- **Net benefit** — realized business impact versus the fixed-threshold baseline
- **Segment threshold table** — current values, with trend indicators between refreshes
- **Decision audit trace** — full reasoning for any single transaction, on demand

---

## Business Impact Equation

```
Net Benefit =

    (Revenue recovered from reduced false declines)
  + (CLV preserved from customers not unnecessarily churned)
  − (Additional fraud loss incurred, if any)
  − (Additional challenge / friction operational cost)
  − (Infrastructure and maintenance cost)

  vs. baseline (fixed global threshold)
```

The system is justified only if it demonstrably reduces false-positive-driven revenue and CLV loss by more than any increase in fraud loss or operational cost.

---

## Testing

| Test Type | Coverage |
|---|---|
| Unit Tests | Cost formulas, segment lookup, version resolution, fallback logic |
| Integration Tests | `/decide` end-to-end, ring-override precedence |
| Shadow Mode | Live traffic diffed against production before cutover |
| Canary Backtest | Every threshold table must pass historical replay before publish |

---

## Requirements

- Python 3.8+
- Dependencies: `pandas`, `scipy`, `numpy`

---

## License

MIT

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Run the full test suite: `python run_all_tests.py`
5. Open a pull request

---

## Authors

Fraud Decision Service Team

---

*"A fixed threshold is not a decision policy — it's a placeholder that happens to work until someone asks why 0.5?"*