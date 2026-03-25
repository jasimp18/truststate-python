"""Data types for the TrustState SDK.

This module defines the result dataclasses returned by TrustStateClient.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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
        feed_label: The feed label from the batch request — useful for multi-feed pipelines.
        mock: True when the result was synthesised locally in mock mode (no HTTP call made).
    """

    passed: bool
    record_id: Optional[str]
    request_id: str
    entity_id: str
    fail_reason: Optional[str]
    failed_step: Optional[int]
    feed_label: Optional[str] = None
    mock: bool = False


@dataclass
class EvidenceItem:
    """A single oracle evidence item to be submitted alongside a write.

    Attributes:
        evidence_id: Unique ID for this evidence item (auto-generated if not provided).
        provider_id: Registered oracle provider ID (e.g. "reuters-fx").
        provider_type: Oracle provider type (e.g. "fx_rate", "kyc_status").
        subject: Key-value dict identifying the data subject (e.g. {"from": "MYR", "to": "USD"}).
        observed_value: The oracle-reported value (numeric or string).
        observed_at: ISO-8601 timestamp when the value was observed by the oracle.
        retrieved_at: ISO-8601 timestamp when you fetched this value (defaults to now).
        max_age_seconds: Maximum acceptable age of this evidence in seconds (default 300).
        proof_hash: Optional sha256:<hex> hash of the raw proof document.
        raw_proof_uri: Optional URL to the raw proof document for background verification.
        attestation: Optional dict with ``type``, ``algorithm``, ``signature`` fields.
        mock: True when synthesised locally (no real oracle call).
    """

    provider_id: str
    provider_type: str
    subject: Dict[str, Any]
    observed_value: Any
    observed_at: str
    evidence_id: str = field(default_factory=lambda: str(_uuid.uuid4()))
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    max_age_seconds: int = 300
    proof_hash: Optional[str] = None
    raw_proof_uri: Optional[str] = None
    attestation: Optional[Dict[str, Any]] = None
    mock: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to the wire format expected by the TrustState API."""
        d: Dict[str, Any] = {
            "evidenceId":     self.evidence_id,
            "providerId":     self.provider_id,
            "providerType":   self.provider_type,
            "subject":        self.subject,
            "observedValue":  self.observed_value,
            "observedAt":     self.observed_at,
            "retrievedAt":    self.retrieved_at,
            "maxAgeSeconds":  self.max_age_seconds,
        }
        if self.proof_hash:
            d["proofHash"] = self.proof_hash
        if self.raw_proof_uri:
            d["rawProofUri"] = self.raw_proof_uri
        if self.attestation:
            d["attestation"] = self.attestation
        return d


@dataclass
class BatchResult:
    """Aggregated result for a batch compliance submission.

    Attributes:
        batch_id: Unique ID for this batch request.
        total: Total number of items submitted.
        accepted: Number of items that passed compliance checks.
        rejected: Number of items that failed compliance checks.
        results: Per-item ComplianceResult list (same order as submitted items).
        feed_label: The feed label for this batch (echoed from request).
        mock: True when running in mock mode (no HTTP calls made).
    """

    batch_id: str
    total: int
    accepted: int
    rejected: int
    results: List[ComplianceResult]
    feed_label: Optional[str] = None
    mock: bool = False
