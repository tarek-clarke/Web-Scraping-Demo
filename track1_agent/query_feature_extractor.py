"""
query_feature_extractor.py — Text query feature extraction for Track 1 VQC routing.

Extracts 10 numerical features from an incoming text query and scales
them to [0, π] for use as rotation angles in the Variational Quantum
Classifier (VQC) circuit. The router uses these features to decide
whether to route a query to a local model (cost = $0 tokens) or to
the remote Fireworks AI API (cost = remote tokens).
"""

from __future__ import annotations

import math
import re
from typing import List

import numpy as np


# Number of features produced by the extractor.
NUM_FEATURES: int = 10

# Code-related markers that signal a query likely needs a stronger model.
_CODE_MARKERS = re.compile(
    r"```|def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import"
    r"|function\s+\w+|\{.*\}|<[a-zA-Z]+>",
    re.DOTALL,
)

# JSON-like structure markers.
_JSON_MARKERS = re.compile(r'[\{\[]\s*"[^"]+"\s*:', re.DOTALL)

# Question complexity keywords.
_COMPLEXITY_WORDS = re.compile(
    r"\b(why|how|explain|compare|contrast|analyze|evaluate|describe"
    r"|differentiate|justify|elaborate|summarize|synthesize)\b",
    re.IGNORECASE,
)


class QueryFeatureExtractor:
    """Extract and encode query-complexity features for quantum routing.

    Each call to :meth:`extract` produces a 10-element vector in [0, π]:

    ======  =======================  ====================================
    Index   Name                     Description
    ======  =======================  ====================================
    0       char_length              Character count, normed by max 2000.
    1       token_estimate           Estimated token count (chars/4),
                                     normed by max 500.
    2       word_count               Word count, normed by max 300.
    3       avg_word_length          Average word length, normed by max 15.
    4       has_code                 Binary: contains code markers.
    5       has_json                 Binary: contains JSON-like structures.
    6       question_complexity      Count of complexity keywords,
                                     normed by max 5.
    7       numeric_density          Ratio of numeric chars to total chars.
    8       punctuation_density      Ratio of punctuation to total chars.
    9       newline_density          Ratio of newlines to total chars,
                                     normed by max 0.1.
    ======  =======================  ====================================
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, query: str) -> np.ndarray:
        """Extract a feature vector from a single text query.

        Parameters
        ----------
        query : str
            The raw text query to analyse.

        Returns
        -------
        np.ndarray
            Shape ``(10,)`` array of floats in ``[0, π]``.
        """
        features = np.zeros(NUM_FEATURES, dtype=np.float64)

        total_chars = len(query)
        if total_chars == 0:
            return features  # All zeros for empty query

        words = query.split()
        word_count = len(words)

        # 0: char_length — normed by 2000
        features[0] = self._normalize(total_chars, 2000.0)

        # 1: token_estimate — rough estimate: chars / 4, normed by 500
        features[1] = self._normalize(total_chars / 4.0, 500.0)

        # 2: word_count — normed by 300
        features[2] = self._normalize(word_count, 300.0)

        # 3: avg_word_length — normed by 15
        if word_count > 0:
            avg_len = sum(len(w) for w in words) / word_count
            features[3] = self._normalize(avg_len, 15.0)

        # 4: has_code — binary
        features[4] = 1.0 if _CODE_MARKERS.search(query) else 0.0

        # 5: has_json — binary
        features[5] = 1.0 if _JSON_MARKERS.search(query) else 0.0

        # 6: question_complexity — count of complexity keywords, normed by 5
        complexity_hits = len(_COMPLEXITY_WORDS.findall(query))
        features[6] = self._normalize(complexity_hits, 5.0)

        # 7: numeric_density — ratio of digits to total chars
        digit_count = sum(1 for c in query if c.isdigit())
        features[7] = digit_count / total_chars

        # 8: punctuation_density — ratio of punctuation to total chars
        punct_count = sum(1 for c in query if c in '.,;:!?()[]{}"\'-/\\@#$%^&*~`')
        features[8] = punct_count / total_chars

        # 9: newline_density — ratio of newlines to total chars, normed by 0.1
        newline_count = query.count("\n")
        raw_density = newline_count / total_chars
        features[9] = self._normalize(raw_density, 0.1)

        # Scale all features from [0, 1] to [0, π]
        features *= math.pi

        return features

    def extract_batch(self, queries: List[str]) -> np.ndarray:
        """Extract features for a batch of queries.

        Parameters
        ----------
        queries : list of str
            List of text queries.

        Returns
        -------
        np.ndarray
            Shape ``(N, 10)`` array.
        """
        return np.array([self.extract(q) for q in queries])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(value: float, max_val: float) -> float:
        """Clamp *value* to ``[0, 1]`` by dividing by *max_val*."""
        if max_val <= 0:
            return 0.0
        return min(max(value / max_val, 0.0), 1.0)
