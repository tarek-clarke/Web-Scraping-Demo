"""
training.py – Training pipeline for the quantum routing module.

Loads MI250X benchmark results from ``data/reports/MI250X/`` CSVs and
determines the best reconciler per (api, chaos_method, chaos_sub_type)
combination based on accuracy and latency trade-offs.  The resulting
labels are consumed by the quantum router's amplitude-encoding step.
"""

import os
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd


class RoutingTrainer:
    """
    Trains the quantum router using historical benchmark data.

    Loads MI250X results from ``data/reports/MI250X/`` CSVs and determines
    the best reconciler per ``(api, chaos_method, chaos_sub_type)``
    combination based on accuracy and latency trade-offs.
    """

    RECONCILER_LABEL_MAP: Dict[str, int] = {
        "levenshtein": 0,
        "regex": 1,
        "bert": 2,
        "gemma_e4b": 3,
    }

    def __init__(self, reports_dir: str = "data/reports/MI250X") -> None:
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
            Explicit path to a ``matrix_results_*.csv``.  When *None* the
            most recent file in ``self.reports_dir`` is used.
        drift_csv : str, optional
            Explicit path to a ``drift_events_*.csv``.  When *None* the
            most recent file in ``self.reports_dir`` is used.
        """
        if matrix_csv is None:
            # Find most recent matrix results file
            files = sorted(
                f for f in os.listdir(self.reports_dir)
                if f.startswith("matrix_results_")
            )
            if not files:
                raise FileNotFoundError(
                    f"No matrix_results CSV found in {self.reports_dir}"
                )
            matrix_csv = os.path.join(self.reports_dir, files[-1])

        if drift_csv is None:
            files = sorted(
                f for f in os.listdir(self.reports_dir)
                if f.startswith("drift_events_")
            )
            if not files:
                raise FileNotFoundError(
                    f"No drift_events CSV found in {self.reports_dir}"
                )
            drift_csv = os.path.join(self.reports_dir, files[-1])

        self.matrix_df = pd.read_csv(matrix_csv)
        self.drift_df = pd.read_csv(drift_csv)
        print(
            f"[RoutingTrainer] Loaded {len(self.matrix_df)} matrix rows, "
            f"{len(self.drift_df)} drift events"
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
            Drop ``gemma_e4b`` rows before ranking (default *True*).

        Returns
        -------
        pd.DataFrame
            Columns: ``api``, ``chaos_method``, ``best_reconciler``,
            ``best_accuracy``, ``best_latency_ms``.
        """
        df = self.matrix_df.copy()

        if exclude_gemma:
            df = df[df["reconciler"] != "gemma_e4b"]

        # Group by api + chaos_method, find reconciler with best accuracy
        best_rows: List[Dict] = []
        for (api, cm), group in df.groupby(["api", "chaos_method"]):
            # Sort by accuracy descending, then latency ascending
            sorted_g = group.sort_values(
                ["accuracy_mean", "gpu_latency_mean_ms"],
                ascending=[False, True],
            )
            best = sorted_g.iloc[0]
            best_rows.append(
                {
                    "api": api,
                    "chaos_method": cm,
                    "best_reconciler": best["reconciler"],
                    "best_accuracy": best["accuracy_mean"],
                    "best_latency_ms": best["gpu_latency_mean_ms"],
                }
            )

        return pd.DataFrame(best_rows)

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
            Exclude ``gemma_e4b`` from ranking.

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

        if exclude_gemma:
            df = df[df["reconciler"] != "gemma_e4b"]

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
