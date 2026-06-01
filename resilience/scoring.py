class ResilienceScoring:
    @staticmethod
    def calculate_raw_p(T: float, D: float, R: float, L: float) -> float:
        """
        Default formula:
        P = 0.35*T + 0.25*D + 0.20*R + 0.20*L
        """
        return 0.35 * T + 0.25 * D + 0.20 * R + 0.20 * L

    @staticmethod
    def calculate_raw_p2(T: float, D: float, R: float, L: float) -> float:
        """
        Improved formula option:
        P2 = 0.30*T + 0.30*D + 0.25*R + 0.15*L
        """
        return 0.30 * T + 0.30 * D + 0.25 * R + 0.15 * L

    @classmethod
    def calculate_scores(cls, throughput_pps: float, target_hz: float, 
                         detection_rate: float, recovery_score: float, 
                         p95_latency_ms: float, baseline_p95_ms: float = 10.0) -> dict:
        """
        Normalizes inputs and calculates both P and P2.
        
        Normalization Rules:
        - T (Throughput Score) = min(1.0, throughput_pps / target_hz)
        - D (Detection Rate) = clamped in [0, 1]
        - R (Recovery Score) = clamped in [0, 1]
        - L (Latency Score) = min(1.0, baseline_p95_ms / max(1e-6, p95_latency_ms))
        """
        # Normalize T (throughput relative to target rate)
        T_norm = min(1.0, max(0.0, throughput_pps / max(1.0, target_hz)))
        
        # Normalize D and R
        D_norm = min(1.0, max(0.0, float(detection_rate)))
        R_norm = min(1.0, max(0.0, float(recovery_score)))
        
        # Normalize L (inverse relative latency compared to baseline)
        L_norm = min(1.0, max(0.0, baseline_p95_ms / max(1e-6, float(p95_latency_ms))))
        
        p = cls.calculate_raw_p(T_norm, D_norm, R_norm, L_norm)
        p2 = cls.calculate_raw_p2(T_norm, D_norm, R_norm, L_norm)
        
        return {
            "T_normalized": T_norm,
            "D_normalized": D_norm,
            "R_normalized": R_norm,
            "L_normalized": L_norm,
            "P": p,
            "P2": p2
        }
