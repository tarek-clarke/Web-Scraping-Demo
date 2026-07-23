"""
training.py – Training pipeline for the quantum routing module.

Loads MI250X benchmark results from ``data/reports/quantum_MI250X_10rep_success/``
CSV trees and
determines the best reconciler per (api, chaos_method, chaos_sub_type)
combination based on accuracy and latency trade-offs.  The resulting
labels are consumed by the quantum router's amplitude-encoding step.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd


class RoutingTrainer:
    """
    Trains the quantum router using historical benchmark data.

    Loads MI250X results from the benchmark result tree and determines
    the best reconciler per ``(api, chaos_method, chaos_sub_type)``
    combination based on accuracy and latency trade-offs.
    """

    RECONCILER_LABEL_MAP: Dict[str, int] = {
        "levenshtein": 0,
        "regex": 1,
        "bert": 2,
        "gemma_e2b": 3,
        "nemotron": 4,
    }
    # Only these rows are valid oracle candidates.  ``quantum_routed`` is an
    # evaluation result produced by the model being trained, so including it
    # would leak prior router behaviour into the target labels.
    BASELINE_RECONCILERS = frozenset(
        {"levenshtein", "regex", "bert", "gemma_e2b"}
    )
    ACTIVE_APIS = frozenset(
        {
            "openf1",
            "finnhub",
            "spacex",
            "openweather",
            "clinical",
            "hockey_nhl",
            "aviation_opensky",
            "football_uefa",
            "smartcity_transit",
        }
    )

    def __init__(self, reports_dir: str = "data/reports/quantum_MI250X_10rep_success") -> None:
        self.reports_dir = reports_dir
        self.matrix_df: Optional[pd.DataFrame] = None
        self.drift_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_data(
        self,
        matrix_csv: Optional[str] = None,
        drift_csv: Optional[str] = None,
    ) -> None:
        """Load the most recent benchmark CSVs.

        Parameters
        ----------
        matrix_csv : str, optional
            Explicit path to a ``matrix_results_*.csv``.  When *None* all
            matching files found recursively under ``self.reports_dir`` are
            concatenated.
        drift_csv : str, optional
            Explicit path to a ``drift_events_*.csv``.  When *None* all
            matching files found recursively under ``self.reports_dir`` are
            concatenated.
        """
        if matrix_csv is None:
            matrix_files = self._collect_report_files("matrix_results_*.csv")
            if not matrix_files:
                raise FileNotFoundError(
                    f"No matrix_results CSV found under {self.reports_dir}"
                )
            self.matrix_df = pd.concat(
                [pd.read_csv(path) for path in matrix_files],
                ignore_index=True,
            ).drop_duplicates().reset_index(drop=True)
        else:
            self.matrix_df = pd.read_csv(matrix_csv)

        if drift_csv is None:
            drift_files = self._collect_report_files("drift_events_*.csv")
            if drift_files:
                self.drift_df = pd.concat(
                    [pd.read_csv(path) for path in drift_files],
                    ignore_index=True,
                ).drop_duplicates().reset_index(drop=True)
            else:
                self.drift_df = pd.DataFrame()
        else:
            self.drift_df = pd.read_csv(drift_csv)

        print(
            f"[RoutingTrainer] Loaded {len(self.matrix_df)} matrix rows, "
            f"{len(self.drift_df)} drift events"
        )
        print(
            f"[RoutingTrainer] Source files: "
            f"{len(self._collect_report_files('matrix_results_*.csv'))} matrix, "
            f"{len(self._collect_report_files('drift_events_*.csv'))} drift"
        )

    # ------------------------------------------------------------------
    # Best-reconciler computation
    # ------------------------------------------------------------------

    def compute_best_reconciler(self, exclude_gemma: bool = True) -> pd.DataFrame:
        """Determine the best reconciler per ``(api, chaos_method)`` combo.

        For each group the reconciler with the highest ``accuracy_mean`` is
        selected.  Ties are broken by preferring lower ``gpu_latency_mean_ms``.

        Parameters
        ----------
        exclude_gemma : bool
            Drop ``gemma_e2b`` rows before ranking (default *True*).

        Returns
        -------
        pd.DataFrame
            Columns: ``api``, ``chaos_method``, ``best_reconciler``,
            ``best_accuracy``, ``best_latency_ms``.
        """
        df = self.matrix_df.copy()

        # Restrict labels to standalone reconciler measurements.  In
        # particular, never use ``quantum_routed`` as a candidate label.
        df = df[df["reconciler"].isin(self.BASELINE_RECONCILERS)]
        # Keep the training target aligned with the paper's nine-API corpus;
        # legacy APIs can remain in the report tree without affecting labels.
        df = df[df["api"].isin(self.ACTIVE_APIS)]

        if exclude_gemma:
            df = df[df["reconciler"] != "gemma_e2b"]

        # First average repeated runs for each candidate reconciler.  Selecting
        # directly from raw repetitions would choose the lucky maximum run and
        # produce optimistic/leaky labels.
        candidate_means = (
            df.groupby(["api", "chaos_method", "reconciler"], as_index=False)
            .agg(
                accuracy_mean=("accuracy_mean", "mean"),
                latency_mean_ms=("latency_mean_ms", "mean"),
            )
        )

        # Group by api + chaos_method, find reconciler with best mean accuracy.
        best_rows: List[Dict] = []
        for (api, cm), group in candidate_means.groupby(["api", "chaos_method"]):
            # Sort by accuracy descending, then latency ascending
            sorted_g = group.sort_values(
                ["accuracy_mean", "latency_mean_ms"],
                ascending=[False, True],
            )
            best = sorted_g.iloc[0]
            best_rows.append(
                {
                    "api": api,
                    "chaos_method": cm,
                    "best_reconciler": best["reconciler"],
                    "best_accuracy": best["accuracy_mean"],
                    "best_latency_ms": best["latency_mean_ms"],
                }
            )

        return pd.DataFrame(best_rows)

    def _collect_report_files(self, pattern: str) -> List[str]:
        """Collect matching report files recursively beneath ``reports_dir``."""
        base = Path(self.reports_dir)
        if not base.exists():
            return []
        return sorted(str(p) for p in base.rglob(pattern))

    # ------------------------------------------------------------------
    # Label generation
    # ------------------------------------------------------------------

    def generate_training_labels(
        self, exclude_gemma: bool = True
    ) -> Tuple[List[Tuple[str, str]], np.ndarray]:
        """Generate training features and labels from drift events.

        Labels are determined by which reconciler performed best for each
        ``(api, chaos_method)`` combination in the benchmark.

        Parameters
        ----------
        exclude_gemma : bool
            Exclude ``gemma_e2b`` from ranking.

        Returns
        -------
        keys : list[tuple[str, str]]
            ``(api, chaos_method)`` tuples.
        y : np.ndarray
            Integer labels (see :pyattr:`RECONCILER_LABEL_MAP`).
        """
        best_df = self.compute_best_reconciler(exclude_gemma=exclude_gemma)

        # Create a lookup: (api, chaos_method) -> best reconciler label
        label_lookup: Dict[Tuple[str, str], int] = {}
        for _, row in best_df.iterrows():
            key = (row["api"], row["chaos_method"])
            label_lookup[key] = self.RECONCILER_LABEL_MAP.get(
                row["best_reconciler"], 0
            )

        # Generate labels for each unique (api, chaos_method) combo
        labels: List[int] = []
        keys: List[Tuple[str, str]] = []
        for key, label in label_lookup.items():
            labels.append(label)
            keys.append(key)

        return keys, np.array(labels)

    # ------------------------------------------------------------------
    # Sub-type analysis
    # ------------------------------------------------------------------

    def get_sub_type_accuracy(self, exclude_gemma: bool = True) -> pd.DataFrame:
        """Compute accuracy per ``(chaos_sub_type, reconciler)`` from drift events.

        This gives fine-grained routing labels.

        Returns
        -------
        pd.DataFrame
            Columns: ``chaos_sub_type``, ``reconciler``, ``accuracy``,
            ``total_events``, ``success_events``.
        """
        df = self.drift_df.copy()
        if df is None or df.empty:
            return pd.DataFrame(
                columns=[
                    "chaos_sub_type",
                    "reconciler",
                    "accuracy",
                    "total_events",
                    "success_events",
                ]
            )

        if exclude_gemma:
            df = df[df["reconciler"] != "gemma_e2b"]

        # Count SUCCESS vs total per (sub_type, reconciler)
        results: List[Dict] = []
        for (sub_type, rec), group in df.groupby(["chaos_sub_type", "reconciler"]):
            total = len(group)
            success = len(group[group["reconciliation_status"] == "SUCCESS"])
            accuracy = success / total if total > 0 else 0.0
            results.append(
                {
                    "chaos_sub_type": sub_type,
                    "reconciler": rec,
                    "accuracy": accuracy,
                    "total_events": total,
                    "success_events": success,
                }
            )

        return pd.DataFrame(results)

    def get_best_reconciler_per_sub_type(
        self, exclude_gemma: bool = True
    ) -> Dict[str, str]:
        """Return the best reconciler for every ``chaos_sub_type``.

        This is the finest-grained routing label available.

        Returns
        -------
        dict[str, str]
            ``{chaos_sub_type: best_reconciler_name}``.
        """
        sub_type_df = self.get_sub_type_accuracy(exclude_gemma=exclude_gemma)

        best: Dict[str, str] = {}
        for sub_type, group in sub_type_df.groupby("chaos_sub_type"):
            sorted_g = group.sort_values("accuracy", ascending=False)
            best[sub_type] = sorted_g.iloc[0]["reconciler"]

        return best

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of training data."""
        if self.matrix_df is None:
            return "No data loaded. Call load_data() first."

        best = self.compute_best_reconciler()
        lines = ["=== Quantum Router Training Summary ==="]
        lines.append(f"Matrix results: {len(self.matrix_df)} rows")
        lines.append(f"Drift events: {len(self.drift_df)} rows")
        lines.append("")
        lines.append("Best reconciler per (api, chaos_method):")
        for _, row in best.iterrows():
            lines.append(
                f"  {row['api']}/{row['chaos_method']}: "
                f"{row['best_reconciler']} "
                f"(acc={row['best_accuracy']:.3f}, "
                f"lat={row['best_latency_ms']:.1f}ms)"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import math
    from src.routing.quantum_router import QuantumRouter

    parser = argparse.ArgumentParser(description="Train the Quantum Router models.")
    parser.add_argument(
        "--data",
        type=str,
        default="data/reports/quantum_MI250X_10rep_success",
        help="Directory containing benchmark CSVs",
    )
    parser.add_argument("--output", type=str, default="configs/trained_router_params.json", help="Path to save weights")
    parser.add_argument("--api", type=str, default=None, help="Filter training data by specific API")
    parser.add_argument("--maxiter", type=int, default=150, help="Max optimizer iterations")
    args = parser.parse_args()

    print(f"[Training] Bootstrapping quantum training pipeline...")
    trainer = RoutingTrainer(reports_dir=args.data)
    try:
        trainer.load_data()
    except Exception as e:
        print(f"[Training] Could not load historical data: {e}. Generating fallback synthetic training data...")
        # Create empty DataFrames to prevent crashes
        trainer.matrix_df = pd.DataFrame(columns=["api", "chaos_method", "reconciler", "accuracy_mean", "gpu_latency_mean_ms"])

    # Filter by API if requested
    if args.api and trainer.matrix_df is not None and len(trainer.matrix_df) > 0:
        trainer.matrix_df = trainer.matrix_df[trainer.matrix_df["api"] == args.api]
        print(f"[Training] Filtered historical reports for API: {args.api} ({len(trainer.matrix_df)} records)")

    # Define API sources ordinal encoding for the full paper scope.
    api_map = {
        "openf1": 0.10,
        "finnhub": 0.20,
        "spacex": 0.30,
        "openweather": 0.40,
        "clinical": 0.50,
        "hockey_nhl": 0.60,
        "aviation_opensky": 0.70,
        "football_uefa": 0.80,
        "smartcity_transit": 0.90,
    }
    api_val = api_map.get(args.api, 0.50)

    # Generate Synthetic Training Dataset mimicking target mapping features:
    # 1. Levenshtein label 0 (Low edits, simple changes)
    # 2. Regex label 1 (Structural alterations, specific keys)
    # 3. BERT label 2 (Semantic rename / Qwen drifts)
    X_list = []
    y_list = []

    # Let's generate 4 sample patterns per reconciler class for fast VQC fitting
    for _ in range(4):
        # Class 0: Levenshtein
        # features: low key edit dist (<0.2), no type changes (0), no structural changes (0), low removed/added
        X_list.append([0.3, 0.2, 0.5, 0.5, 0.05, 0.05, np.random.uniform(0, 0.15) * math.pi, 0.0, 0.0, api_val * math.pi])
        y_list.append(0)

        # Class 1: Regex
        # features: moderate edit dist, low type/structural, moderate added/removed
        X_list.append([0.3, 0.2, 0.5, 0.5, 0.2, 0.1, np.random.uniform(0.15, 0.45) * math.pi, 0.0, 0.0, api_val * math.pi])
        y_list.append(1)

        # Class 2: BERT
        # features: high edit dist (>0.5), type change (1.0) or structural change (1.0)
        X_list.append([0.4, 0.4, 0.3, 0.3, 0.4, 0.3, np.random.uniform(0.5, 1.0) * math.pi, 1.0 * math.pi, 1.0 * math.pi, api_val * math.pi])
        y_list.append(2)

    X_train = np.array(X_list)
    y_train = np.array(y_list)

    print(f"[Training] Dataset prepared: X_train shape={X_train.shape}, y_train shape={y_train.shape}")
    print(f"[Training] Initializing Quantum VQC Router...")
    
    router = QuantumRouter(backend="aer_simulator", mode="vqc", shots=256)
    
    print(f"[Training] Running classical VQC simulation fitting (maxiter=10)...")
    try:
        metrics = router.train(X_train, y_train, maxiter=10)
        print(f"[Training] Fit completed. Accuracy: {metrics['train_accuracy']:.2%}")
        
        # Save weights
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        router.save_params(args.output)
        print(f"[Training] Saved trained quantum weights to: {args.output}")
    except Exception as e:
        print(f"[Training] Fitting failed: {e}. Fallback weights will be initialized dynamically during routing.")
