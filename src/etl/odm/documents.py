"""Compatibility wrapper for ODM documents.

The concrete document models now live under :mod:`src.domain.documents`.
Importing from this module remains supported for backwards compatibility.
"""
from __future__ import annotations

from ...domain.documents import *  # noqa: F401,F403
