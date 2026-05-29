"""Established resilience scoring system for reproducible research.

Formulas:
- P = 0.35 * T + 0.25 * D + 0.20 * R + 0.20 * L
- P2 = 0.30 * T + 0.30 * D + 0.25 * R + 0.15 * L

Normalization Rules:
- T (Throughput Score) = min(1.0, throughput_pps / target_hz)
- D (Detection Rate) = clamped in [0, 1]
- R (Recovery Score) = clamped in [0, 1]
- L (Latency Score) = min(1.0, baseline_p95_ms / max(1e-6, p95_latency_ms))
"""

from typing import Dict, List, Any

def calculate_scores(
    throughput_pps: float,
    target_hz: float,
    detection_rate: float,
    recovery_score: float,
    p95_latency_ms: float,
    baseline_p95_ms: float = 10.0,
) -> Dict[str, float]:
    """Calculate normalized resilience scores P and P2."""
    T_norm = min(1.0, max(0.0, throughput_pps / max(1.0, target_hz)))
    D_norm = min(1.0, max(0.0, float(detection_rate)))
    R_norm = min(1.0, max(0.0, float(recovery_score)))
    L_norm = min(1.0, max(0.0, baseline_p95_ms / max(1e-6, float(p95_latency_ms))))
    
    p = 0.35 * T_norm + 0.25 * D_norm + 0.20 * R_norm + 0.20 * L_norm
    p2 = 0.30 * T_norm + 0.30 * D_norm + 0.25 * R_norm + 0.15 * L_norm
    
    return {
        "T_normalized": T_norm,
        "D_normalized": D_norm,
        "R_normalized": R_norm,
        "L_normalized": L_norm,
        "P": p,
        "P2": p2,
    }

class ResilienceEvaluator:
    """Helper to aggregate resilience metrics across multiple runs, drift types, and methods."""
    
    def __init__(self):
        self.runs: List[Dict[str, Any]] = []

    def add_run(
        self,
        run_id: str,
        drift_type: str,
        method: str,
        throughput_pps: float,
        target_hz: float,
        detection_rate: float,
        recovery_score: float,
        p95_latency_ms: float,
        baseline_p95_ms: float = 10.0,
    ) -> Dict[str, float]:
        scores = calculate_scores(
            throughput_pps=throughput_pps,
            target_hz=target_hz,
            detection_rate=detection_rate,
            recovery_score=recovery_score,
            p95_latency_ms=p95_latency_ms,
            baseline_p95_ms=baseline_p95_ms,
        )
        run_data = {
            "run_id": run_id,
            "drift_type": drift_type,
            "method": method,
            **scores,
        }
        self.runs.append(run_data)
        return scores

    def get_summary(self) -> Dict[str, Any]:
        """Aggregate scores per run, per drift type, and per method."""
        if not self.runs:
            return {}

        global_p = [r["P"] for r in self.runs]
        global_p2 = [r["P2"] for r in self.runs]
        
        # Group by drift type
        drift_scores: Dict[str, List[float]] = {}
        for r in self.runs:
            dt = r["drift_type"] or "none"
            drift_scores.setdefault(dt, []).append(r["P"])

        # Group by method
        method_scores: Dict[str, List[float]] = {}
        for r in self.runs:
            m = r["method"]
            method_scores.setdefault(m, []).append(r["P"])

        return {
            "global_resilience_mean_P": sum(global_p) / len(global_p),
            "global_resilience_mean_P2": sum(global_p2) / len(global_p2),
            "by_drift_type": {
                dt: sum(scores) / len(scores) for dt, scores in drift_scores.items()
            },
            "by_method": {
                m: sum(scores) / len(scores) for m, scores in method_scores.items()
            },
        }
