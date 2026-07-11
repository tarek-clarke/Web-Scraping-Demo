"""Feature extraction for quantum angle encoding.

Extracts 10 numerical features from a pair of data dictionaries
(original vs. drifted) and scales them to [0, π] for use as
rotation angles in parameterised quantum circuits.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import Levenshtein
import numpy as np


# Ordinal encoding map for known data sources.
_SOURCE_ENCODING: Dict[str, float] = {
    "clinical": 0.20,
    "openf1": 0.40,
    "finnhub": 0.60,
    "spacex": 0.80,
    "openweather": 1.00,
}

# Number of features produced by the extractor.
NUM_FEATURES: int = 10


class FeatureExtractor:
    """Extract and encode drift-detection features for quantum routing.

    Each call to :meth:`extract` produces a 10-element vector in [0, π]:

    ======  ===========================  ====================================
    Index   Name                         Description
    ======  ===========================  ====================================
    0       field_count                  Number of keys in *original*, normed
                                         by max 50.
    1       nesting_depth                Max nesting depth of *original*,
                                         normed by max 5.
    2       numeric_ratio                Fraction of *original* values that
                                         are ``int`` or ``float``.
    3       string_ratio                 Fraction of *original* values that
                                         are ``str``.
    4       fields_added                 Keys in *drifted* but not in
                                         *original*, normed by field count.
    5       fields_removed               Keys in *original* but not in
                                         *drifted*, normed by field count.
    6       key_edit_distance_mean       Mean best-match Levenshtein distance
                                         between key sets, normed by max 10.
    7       has_type_changes             Binary: any shared key changed type?
    8       has_structural_changes       Binary: nesting depth changed or
                                         arrays appeared / disappeared?
    9       source_encoded               Ordinal encoding of the data source.
    ======  ===========================  ====================================
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        original_data: Dict[str, Any],
        drifted_data: Dict[str, Any],
        source: str = "unknown",
    ) -> np.ndarray:
        """Return a (10,) float64 array of features scaled to [0, π].

        Parameters
        ----------
        original_data:
            The baseline / reference data record.
        drifted_data:
            The potentially-drifted data record.
        source:
            Name of the upstream data source (e.g. ``"openf1"``).

        Returns
        -------
        np.ndarray
            Shape ``(10,)`` with values in ``[0, π]``.
        """
        original_keys = set(original_data.keys())
        drifted_keys = set(drifted_data.keys())
        field_count = len(original_keys)

        # --- 0. field_count ------------------------------------------------
        f_field_count = self._normalize(float(field_count), max_val=50.0)

        # --- 1. nesting_depth ----------------------------------------------
        depth = self._compute_nesting_depth(original_data)
        f_nesting_depth = self._normalize(float(depth), max_val=5.0)

        # --- 2. numeric_ratio ----------------------------------------------
        f_numeric_ratio = self._value_type_ratio(original_data, (int, float))

        # --- 3. string_ratio -----------------------------------------------
        f_string_ratio = self._value_type_ratio(original_data, (str,))

        # --- 4. fields_added -----------------------------------------------
        added = drifted_keys - original_keys
        f_fields_added = (
            self._normalize(float(len(added)), max_val=float(field_count))
            if field_count > 0
            else 0.0
        )

        # --- 5. fields_removed ---------------------------------------------
        removed = original_keys - drifted_keys
        f_fields_removed = (
            self._normalize(float(len(removed)), max_val=float(field_count))
            if field_count > 0
            else 0.0
        )

        # --- 6. key_edit_distance_mean -------------------------------------
        f_key_edit_dist = self._mean_best_key_edit_distance(
            original_keys, drifted_keys
        )

        # --- 7. has_type_changes -------------------------------------------
        shared_keys = original_keys & drifted_keys
        f_has_type_changes = 0.0
        for key in shared_keys:
            if type(original_data[key]) is not type(drifted_data[key]):  # noqa: E721
                f_has_type_changes = 1.0
                break

        # --- 8. has_structural_changes -------------------------------------
        drifted_depth = self._compute_nesting_depth(drifted_data)
        depth_changed = depth != drifted_depth

        arrays_changed = False
        for key in shared_keys:
            orig_is_list = isinstance(original_data[key], list)
            drift_is_list = isinstance(drifted_data[key], list)
            if orig_is_list != drift_is_list:
                arrays_changed = True
                break

        f_has_structural = 1.0 if (depth_changed or arrays_changed) else 0.0

        # --- 9. source_encoded ---------------------------------------------
        f_source = _SOURCE_ENCODING.get(source.lower(), 0.0)

        # --- Assemble & scale to [0, π] ------------------------------------
        raw = np.array(
            [
                f_field_count,
                f_nesting_depth,
                f_numeric_ratio,
                f_string_ratio,
                f_fields_added,
                f_fields_removed,
                f_key_edit_dist,
                f_has_type_changes,
                f_has_structural,
                f_source,
            ],
            dtype=np.float64,
        )

        return raw * math.pi

    def extract_batch(
        self,
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
        sources: List[str],
    ) -> np.ndarray:
        """Extract features for multiple data-pair samples.

        Parameters
        ----------
        pairs:
            A list of ``(original_data, drifted_data)`` tuples.
        sources:
            A list of source names, one per pair.

        Returns
        -------
        np.ndarray
            Shape ``(N, 10)`` with values in ``[0, π]``.
        """
        rows: List[np.ndarray] = [
            self.extract(orig, drift, src)
            for (orig, drift), src in zip(pairs, sources)
        ]
        return np.stack(rows, axis=0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_nesting_depth(d: Any, depth: int = 0) -> int:
        """Return the maximum nesting depth of *d*.

        Dicts and lists are considered nesting containers.  All other
        types contribute zero additional depth.

        Parameters
        ----------
        d:
            The object to inspect (typically a ``dict`` or ``list``).
        depth:
            Current recursion depth (used internally).

        Returns
        -------
        int
            Maximum depth found (0 for a flat dict with no nested
            containers).
        """
        if isinstance(d, dict):
            if not d:
                return depth
            return max(
                FeatureExtractor._compute_nesting_depth(v, depth + 1)
                for v in d.values()
            )
        if isinstance(d, list):
            if not d:
                return depth
            return max(
                FeatureExtractor._compute_nesting_depth(item, depth + 1)
                for item in d
            )
        return depth

    @staticmethod
    def _normalize(value: float, max_val: float) -> float:
        """Clamp *value* into ``[0, 1]`` by dividing by *max_val*.

        Parameters
        ----------
        value:
            Raw numeric value.
        max_val:
            Maximum expected value (used as the divisor).

        Returns
        -------
        float
            Value in ``[0.0, 1.0]``.
        """
        if max_val <= 0.0:
            return 0.0
        return min(max(value / max_val, 0.0), 1.0)

    # ------------------------------------------------------------------
    # Additional private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _value_type_ratio(
        data: Dict[str, Any], types: Tuple[type, ...]
    ) -> float:
        """Return the fraction of top-level values matching *types*.

        Parameters
        ----------
        data:
            The dictionary whose values are inspected.
        types:
            A tuple of types to check via ``isinstance``.

        Returns
        -------
        float
            Ratio in ``[0.0, 1.0]``.  Returns ``0.0`` for empty dicts.
        """
        if not data:
            return 0.0
        count = sum(1 for v in data.values() if isinstance(v, types))
        return count / len(data)

    @staticmethod
    def _mean_best_key_edit_distance(
        keys_a: set[str], keys_b: set[str]
    ) -> float:
        """Compute the mean of the best-match Levenshtein distances.

        For every key in *keys_a*, find the closest key in *keys_b*
        (minimum edit distance) and return the mean of those minima,
        normalised by a maximum of 10.

        Parameters
        ----------
        keys_a:
            First set of dictionary keys (typically from *original*).
        keys_b:
            Second set of dictionary keys (typically from *drifted*).

        Returns
        -------
        float
            Normalised mean distance in ``[0.0, 1.0]``.
        """
        if not keys_a or not keys_b:
            return 0.0

        best_distances: List[int] = []
        for ka in keys_a:
            min_dist = min(Levenshtein.distance(ka, kb) for kb in keys_b)
            best_distances.append(min_dist)

        mean_dist = sum(best_distances) / len(best_distances)
        return FeatureExtractor._normalize(mean_dist, max_val=10.0)
