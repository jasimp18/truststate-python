"""TrustStateClient — async HTTP client for the TrustState compliance API.

Usage::

    from truststate import TrustStateClient

    client = TrustStateClient(api_key="your-key")
    result = await client.check("AgentResponse", {"text": "...", "score": 0.9})
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

import httpx

from .exceptions import TrustStateError
from .types import BatchResult, ComplianceResult, EvidenceItem


class TrustStateClient:
    """Async client for the TrustState compliance validation API.

    Args:
        api_key: Your TrustState API key (used as X-API-Key header for writes).
        base_url: Override the default API base URL.
        default_schema_version: Schema version applied when not specified per-call.
        default_actor_id: Actor ID applied when not specified per-call.
        mock: If True, all HTTP calls are skipped and synthetic results are returned.
        mock_pass_rate: Probability (0.0–1.0) that a mock check returns passed=True.
            1.0 = always pass, 0.0 = always fail, 0.8 = 80% pass rate.
        timeout: HTTP request timeout in seconds.
    """

    DEFAULT_BASE_URL = "https://truststate-api.apps.trustchainlabs.com"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        default_schema_version: Optional[str] = None,
        default_actor_id: str = "",
        mock: bool = False,
        mock_pass_rate: float = 1.0,
        timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_schema_version = default_schema_version
        self._default_actor_id = default_actor_id
        self._mock = mock
        self._mock_pass_rate = float(mock_pass_rate)
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check(
        self,
        entity_type: str,
        data: Dict[str, Any],
        action: str = "CREATE",
        entity_id: Optional[str] = None,
        schema_version: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> ComplianceResult:
        """Submit a single record for compliance checking.

        Internally wraps the record in a one-item batch and calls POST /v1/write/batch.

        Args:
            entity_type: The type/category of the entity (e.g. "AgentResponse").
            data: The record payload to validate.
            action: The action being performed — "CREATE", "UPDATE", or "DELETE".
            entity_id: Optional stable identifier for this entity. Auto-generated (uuid4)
                if not provided.
            schema_version: Override the client's default schema version.
            actor_id: Override the client's default actor ID.

        Returns:
            ComplianceResult with pass/fail status and, if passed, a record_id.

        Raises:
            TrustStateError: On HTTP 4xx/5xx responses.
        """
        eid = entity_id or str(uuid.uuid4())

        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return self._mock_single_result(eid)

        batch_result = await self.check_batch(
            items=[
                {
                    "entity_type": entity_type,
                    "data": data,
                    "action": action,
                    "entity_id": eid,
                    "schema_version": schema_version,
                    "actor_id": actor_id,
                }
            ],
            default_schema_version=schema_version,
            default_actor_id=actor_id,
        )
        return batch_result.results[0]

    async def check_batch(
        self,
        items: List[Dict[str, Any]],
        default_schema_version: Optional[str] = None,
        default_actor_id: Optional[str] = None,
        feed_label: Optional[str] = None,
    ) -> BatchResult:
        """Submit multiple records for compliance checking in a single API call.

        Args:
            items: List of item dicts. Each may contain:
                - entity_type (required)
                - data (required)
                - action (optional, default "upsert")
                - entity_id (optional, auto-generated if absent)
                - schema_version (optional — server auto-resolves to active schema if omitted)
                - actor_id (optional)
            default_schema_version: Fallback schema version for items that don't specify one.
                If None, the server auto-resolves to the active schema for each entity type.
            default_actor_id: Fallback actor ID for items that don't specify one.
            feed_label: Optional label identifying this feed/source (e.g. "core-banking-feed").
                Echoed back on every item result — useful for multi-feed pipelines.

        Returns:
            BatchResult summarising acceptance/rejection counts and per-item results.

        Raises:
            TrustStateError: On HTTP 4xx/5xx responses.
        """
        schema_ver = default_schema_version or self._default_schema_version
        actor = default_actor_id or self._default_actor_id

        # Normalise items and assign missing entity IDs
        normalised = []
        for item in items:
            eid = item.get("entity_id") or str(uuid.uuid4())
            entry: Dict[str, Any] = {
                "entityType": item["entity_type"],
                "data": item["data"],
                "action": item.get("action", "upsert"),
                "entityId": eid,
                "actorId": item.get("actor_id") or actor or "sdk-writer",
            }
            sv = item.get("schema_version") or schema_ver
            if sv:
                entry["schemaVersion"] = sv
            normalised.append(entry)

        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return self._mock_batch_result(normalised, feed_label=feed_label)

        payload: Dict[str, Any] = {"items": normalised}
        if default_actor_id or self._default_actor_id:
            payload["defaultActorId"] = default_actor_id or self._default_actor_id
        if schema_ver:
            payload["defaultSchemaVersion"] = schema_ver
        if feed_label:
            payload["feedLabel"] = feed_label

        response_json = await self._post("/v1/write/batch", payload)
        return self._parse_batch_response(response_json)

    # ------------------------------------------------------------------
    # BYOP Evidence fetch helpers
    # ------------------------------------------------------------------

    async def fetch_fx_rate(
        self,
        from_currency: str,
        to_currency: str,
        provider_id: str = "reuters-fx",
        max_age_seconds: int = 300,
    ) -> EvidenceItem:
        """Fetch an FX rate oracle evidence item.

        In mock mode returns a deterministic stub value (MYR/USD = 4.72).

        Args:
            from_currency: Source currency code (e.g. "MYR").
            to_currency:   Target currency code (e.g. "USD").
            provider_id:   Oracle provider ID (default "reuters-fx").
            max_age_seconds: Max acceptable age in seconds (default 300).

        Returns:
            EvidenceItem ready to pass to check() or check_batch().
        """
        subject = {"from": from_currency, "to": to_currency}
        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            stub_rates = {"MYR_USD": 0.2119, "USD_MYR": 4.72, "EUR_USD": 1.085, "GBP_USD": 1.267}
            key = f"{from_currency}_{to_currency}"
            value = stub_rates.get(key, 1.0)
            return EvidenceItem(
                provider_id=provider_id,
                provider_type="fx_rate",
                subject=subject,
                observed_value=value,
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                max_age_seconds=max_age_seconds,
                mock=True,
            )
        data = await self._get(f"/v1/oracle/fx-rate?from={from_currency}&to={to_currency}&providerId={provider_id}")
        return EvidenceItem(
            provider_id=data.get("providerId", provider_id),
            provider_type="fx_rate",
            subject=subject,
            observed_value=data["observedValue"],
            observed_at=data["observedAt"],
            max_age_seconds=max_age_seconds,
            proof_hash=data.get("proofHash"),
            raw_proof_uri=data.get("rawProofUri"),
            attestation=data.get("attestation"),
        )

    async def fetch_kyc_status(
        self,
        subject_id: str,
        provider_id: str = "sumsub-kyc",
        max_age_seconds: int = 86400,
    ) -> EvidenceItem:
        """Fetch a KYC status oracle evidence item.

        Args:
            subject_id:    The entity/wallet/account being KYC-checked.
            provider_id:   Oracle provider ID (default "sumsub-kyc").
            max_age_seconds: Max acceptable age (default 86400 = 24h).
        """
        subject = {"id": subject_id}
        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return EvidenceItem(
                provider_id=provider_id,
                provider_type="kyc_status",
                subject=subject,
                observed_value="PASS",
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                max_age_seconds=max_age_seconds,
                mock=True,
            )
        data = await self._get(f"/v1/oracle/kyc-status?subjectId={subject_id}&providerId={provider_id}")
        return EvidenceItem(
            provider_id=data.get("providerId", provider_id),
            provider_type="kyc_status",
            subject=subject,
            observed_value=data["observedValue"],
            observed_at=data["observedAt"],
            max_age_seconds=max_age_seconds,
            proof_hash=data.get("proofHash"),
            attestation=data.get("attestation"),
        )

    async def fetch_credit_score(
        self,
        subject_id: str,
        provider_id: str = "coface-credit",
        max_age_seconds: int = 86400,
    ) -> EvidenceItem:
        """Fetch a credit score oracle evidence item.

        Args:
            subject_id:    Entity being scored.
            provider_id:   Oracle provider ID (default "coface-credit").
            max_age_seconds: Max acceptable age (default 86400 = 24h).
        """
        subject = {"id": subject_id}
        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return EvidenceItem(
                provider_id=provider_id,
                provider_type="credit_score",
                subject=subject,
                observed_value=720,
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                max_age_seconds=max_age_seconds,
                mock=True,
            )
        data = await self._get(f"/v1/oracle/credit-score?subjectId={subject_id}&providerId={provider_id}")
        return EvidenceItem(
            provider_id=data.get("providerId", provider_id),
            provider_type="credit_score",
            subject=subject,
            observed_value=data["observedValue"],
            observed_at=data["observedAt"],
            max_age_seconds=max_age_seconds,
            proof_hash=data.get("proofHash"),
            attestation=data.get("attestation"),
        )

    async def fetch_sanctions(
        self,
        subject_id: str,
        provider_id: str = "refinitiv-sanct",
        max_age_seconds: int = 3600,
    ) -> EvidenceItem:
        """Fetch a sanctions screening oracle evidence item."""
        subject = {"id": subject_id}
        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return EvidenceItem(
                provider_id=provider_id,
                provider_type="sanctions",
                subject=subject,
                observed_value="CLEAR",
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                max_age_seconds=max_age_seconds,
                mock=True,
            )
        data = await self._get(f"/v1/oracle/sanctions?subjectId={subject_id}&providerId={provider_id}")
        return EvidenceItem(
            provider_id=data.get("providerId", provider_id),
            provider_type="sanctions",
            subject=subject,
            observed_value=data["observedValue"],
            observed_at=data["observedAt"],
            max_age_seconds=max_age_seconds,
            proof_hash=data.get("proofHash"),
            attestation=data.get("attestation"),
        )

    async def check_with_evidence(
        self,
        entity_type: str,
        data: Dict[str, Any],
        evidence: List[EvidenceItem],
        action: str = "CREATE",
        entity_id: Optional[str] = None,
        schema_version: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> ComplianceResult:
        """Submit a compliance check with oracle evidence attached.

        Convenience wrapper around check() that serialises EvidenceItem objects
        and bundles them in the write payload.

        Example::

            fx = await client.fetch_fx_rate("MYR", "USD")
            kyc = await client.fetch_kyc_status("0x1234abcd")
            result = await client.check_with_evidence(
                "SukukBond",
                {"issuerId": "...", "faceValue": 500000, "currency": "MYR"},
                evidence=[fx, kyc],
            )
        """
        eid = entity_id or str(uuid.uuid4())
        schema_ver = schema_version or self._default_schema_version
        actor = actor_id or self._default_actor_id

        # Enforce actor_id presence per-item or default on the client
        missing = [e for e in normalised if not e.get(actorId)]
        if missing:
            raise TrustStateError('actor_id is required for all writes. Provide actor_id per-item or set default_actor_id when constructing the client.')

        if self._mock:
            return self._mock_single_result(eid)

        item: Dict[str, Any] = {
            "entityType": entity_type,
            "data":       data,
            "action":     action,
            "entityId":   eid,
            "actorId":    actor or "sdk-writer",
            "evidence":   [e.to_dict() for e in evidence],
        }
        if schema_ver:
            item["schemaVersion"] = schema_ver
        payload = {"items": [item]}
        response_json = await self._post("/v1/write/batch", payload)
        return self._parse_batch_response(response_json).results[0]

    async def verify(self, record_id: str, bearer_token: str) -> Dict[str, Any]:
        """Retrieve an immutable compliance record from the ledger.

        Args:
            record_id: The record ID returned by a previous check() that passed.
            bearer_token: A valid Bearer token for the TrustState API.

        Returns:
            The full record dict from the API.

        Raises:
            TrustStateError: On HTTP 4xx/5xx responses.
        """
        url = f"{self._base_url}/v1/records/{record_id}"
        headers = {"Authorization": f"Bearer {bearer_token}"}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise TrustStateError(f"Network error: {exc}") from exc

        if resp.status_code >= 400:
            raise TrustStateError(
                f"API error {resp.status_code}: {resp.text}", resp.status_code
            )

        return resp.json()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str) -> Dict[str, Any]:
        """Make an authenticated GET request and return the JSON response body."""
        url = f"{self._base_url}{path}"
        headers = {"X-API-Key": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise TrustStateError(f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            raise TrustStateError(f"API error {resp.status_code}: {resp.text}", resp.status_code)
        return resp.json()

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make an authenticated POST request and return the JSON response body."""
        url = f"{self._base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise TrustStateError(f"Network error: {exc}") from exc

        if resp.status_code >= 400:
            raise TrustStateError(
                f"API error {resp.status_code}: {resp.text}", resp.status_code
            )

        return resp.json()

    def _parse_batch_response(self, data: Dict[str, Any]) -> BatchResult:
        """Convert raw API JSON into a BatchResult."""
        raw_results = data.get("results", [])
        results = []
        for r in raw_results:
            accepted = r.get("status") == "accepted"
            results.append(
                ComplianceResult(
                    passed=accepted,
                    record_id=r.get("recordId"),
                    request_id=r.get("requestId", ""),
                    entity_id=r.get("entityId", ""),
                    fail_reason=r.get("failReason"),
                    failed_step=r.get("failedStep"),
                    feed_label=r.get("feedLabel"),
                    mock=False,
                )
            )

        return BatchResult(
            batch_id=data.get("batchId", str(uuid.uuid4())),
            total=data.get("total", len(results)),
            accepted=data.get("accepted", sum(1 for r in results if r.passed)),
            rejected=data.get("rejected", sum(1 for r in results if not r.passed)),
            results=results,
            feed_label=data.get("feedLabel"),
            mock=False,
        )

    # ------------------------------------------------------------------
    # Mock helpers (no network calls)
    # ------------------------------------------------------------------

    def _mock_single_result(self, entity_id: str) -> ComplianceResult:
        """Generate a synthetic ComplianceResult for mock mode."""
        passed = random.random() < self._mock_pass_rate
        return ComplianceResult(
            passed=passed,
            record_id=f"mock-rec-{uuid.uuid4()}" if passed else None,
            request_id=f"mock-req-{uuid.uuid4()}",
            entity_id=entity_id,
            fail_reason=None if passed else "Mock: simulated policy failure",
            failed_step=None if passed else 9,
            mock=True,
        )

    def _mock_batch_result(self, normalised_items: List[Dict[str, Any]], feed_label: Optional[str] = None) -> BatchResult:
        """Generate a synthetic BatchResult for mock mode."""
        results = [
            self._mock_single_result(item["entityId"]) for item in normalised_items
        ]
        for r in results:
            r.feed_label = feed_label
        accepted = sum(1 for r in results if r.passed)
        return BatchResult(
            batch_id=f"mock-batch-{uuid.uuid4()}",
            total=len(results),
            accepted=accepted,
            rejected=len(results) - accepted,
            results=results,
            feed_label=feed_label,
            mock=True,
        )
