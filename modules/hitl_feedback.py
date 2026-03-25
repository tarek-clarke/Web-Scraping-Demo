#!/usr/bin/env python3
# Copyright (c) 2026 Tarek Clarke. All rights reserved.

"""
HITL Feedback Manager
=====================
Research component for "Human-governed Semantic Refinement".
Stores manual corrections to schema drift and provides a primary
lookup for the EnhancedSemanticTranslator.
"""

import json
import os
from typing import Dict, Optional

class HITLFeedbackManager:
    def __init__(self, storage_path: str = "data/hitl_feedback.json"):
        self.storage_path = storage_path
        self._ensure_storage()
        self.feedback = self._load_feedback()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump({}, f)

    def _load_feedback(self) -> Dict[str, str]:
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def add_correction(self, drifted: str, canonical: str):
        """
        Record a human-validated mapping.
        """
        self.feedback[drifted] = canonical
        with open(self.storage_path, "w") as f:
            json.dump(self.feedback, f, indent=4)

    def get_correction(self, drifted: str) -> Optional[str]:
        """
        Check if a human override exists for this field.
        """
        return self.feedback.get(drifted)

if __name__ == "__main__":
    manager = HITLFeedbackManager()
    manager.add_correction("velocity_kph", "speed")
    print(f"Override for 'velocity_kph': {manager.get_correction('velocity_kph')}")
