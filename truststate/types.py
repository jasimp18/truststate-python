"""Data types for the TrustState SDK.

This module defines the result dataclasses returned by TrustStateClient.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ComplianceResult:
    """Result of a single compliance check.

    Attributes:
        passed: True if the record passed all compliance checks.
        record_id: Immutable ledger record ID — only set when passed=True.
        request_id: Unique ID for this API request (useful for support/debugging).
        entity_id: The entity ID that was submitted (caller-supplied or auto-generated).
        fail_reason: Human-readable reason for failure — only set when passed=False.
        failed_step: Numeric step that failed (8=schema validation, 9=policy check).
        mock: True when the result was synthesised locally in mock mode (no HTTP call made).
    """

    passed: bool
    record_id: Optional[str]
    request_id: str
    entity_id: str
    fail_reason: Optional[str]
    failed_step: Optional[int]
    mock: bool = False


@dataclass
class BatchResult:
    """Aggregated result for a batch compliance submission.

    Attributes:
        batch_id: Unique ID for this batch request.
        total: Total number of items submitted.
        accepted: Number of items that passed compliance checks.
        rejected: Number of items that failed compliance checks.
        results: Per-item ComplianceResult list (same order as submitted items).
        mock: True when running in mock mode (no HTTP calls made).
    """

    batch_id: str
    total: int
    accepted: int
    rejected: int
    results: List[ComplianceResult]
    mock: bool = False
