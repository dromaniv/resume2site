"""
Utility functions for the resume2site app.
"""

import hashlib


def _sha(text: str) -> str:
    """Computes SHA256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
