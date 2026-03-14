# ADR-002: Circuit Breaker over Retry Loop for Telemetry Validation

**Status:** Accepted  
**Date:** 2026-01-18  
**Decision-makers:** Tarek Clarke  

## Context

Corrupted telemetry packets (bit-flips, schema drift, NaN injection) must be
isolated before they reach the simulation models.  Two patterns were considered:

| Pattern | Behaviour under sustained corruption |
|---------|--------------------------------------|
| **Retry loop** | Retries each bad packet N times, then discards.  During a burst of corrupt data (e.g., sensor firmware crash), every packet pays the retry penalty — latency explodes and the pit wall feed stalls. |
| **Circuit breaker** | After K consecutive failures, the breaker trips to OPEN.  All subsequent packets are immediately routed to the DLQ without validation overhead.  After a cooldown period, HALF_OPEN lets a single probe through.  If the probe passes, the breaker resets to CLOSED and normal flow resumes. |

## Decision

Implement a **three-state circuit breaker** (CLOSED → OPEN → HALF_OPEN) with
a configurable failure threshold and cooldown window.

## Rationale

1. **Latency budget.**  During a race, the pit wall needs sub-second
   telemetry.  A retry loop with backoff can add seconds of latency per
   packet during a corruption burst.  The circuit breaker adds zero latency
   once tripped — packets go straight to the DLQ.

2. **Graceful degradation.**  The DLQ preserves every quarantined packet for
   post-race forensics.  Nothing is discarded — the data is simply diverted
   from the live feed.

3. **Self-healing.**  The HALF_OPEN probe automatically tests whether the
   upstream corruption has cleared.  No human intervention is needed to
   restore normal operation.

4. **Observability.**  The breaker's state transitions are logged and
   surfaced on the health monitor dashboard.  The pit wall engineer can
   see at a glance whether the circuit is healthy.

## Consequences

- **Pro:** Protects simulation models from garbage data with zero latency
  overhead during corruption bursts.
- **Pro:** DLQ ensures no data loss — quarantined packets can be reprocessed
  after the race with corrected schemas.
- **Con:** Requires careful tuning of `failure_threshold` and
  `cooldown_seconds`.  Too aggressive: breaker trips on transient noise.
  Too lenient: bad data leaks through.  Current defaults (threshold=5,
  cooldown=30s) were validated against triple-header stress tests with 15%
  chaos injection.

## References

- Martin Fowler, "Circuit Breaker": https://martinfowler.com/bliki/CircuitBreaker.html
- `src/circuit_breaker.py` — implementation
- `tools/telemetry_stress_test.py` — validation harness
