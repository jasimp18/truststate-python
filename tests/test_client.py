"""Unit tests for TrustStateClient.

Run with: pytest tests/test_client.py -v
"""

from __future__ import annotations

import asyncio
import pytest
from truststate import TrustStateClient
from truststate.types import ComplianceResult, BatchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine in a new event loop (compatibility helper)."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_mock_client(mock_pass_rate: float = 1.0) -> TrustStateClient:
    return TrustStateClient(
        api_key="test-key",
        mock=True,
        mock_pass_rate=mock_pass_rate,
    )


SAMPLE_DATA = {"responseText": "Hello", "confidenceScore": 0.9}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMockMode:
    """Tests that run entirely in mock mode — no network calls required."""

    def test_check_passes_in_mock_mode(self):
        """check() returns a passing ComplianceResult when mock_pass_rate=1.0."""
        client = make_mock_client(mock_pass_rate=1.0)
        result = run(client.check("AgentResponse", SAMPLE_DATA))

        assert isinstance(result, ComplianceResult)
        assert result.passed is True
        assert result.record_id is not None
        assert result.record_id.startswith("mock-rec-")
        assert result.fail_reason is None
        assert result.failed_step is None
        assert result.mock is True

    def test_check_batch_in_mock_mode(self):
        """check_batch() returns a BatchResult with mock=True for all results."""
        client = make_mock_client(mock_pass_rate=1.0)
        items = [
            {"entity_type": "Tx", "data": {"amount": 100}},
            {"entity_type": "Tx", "data": {"amount": 200}},
            {"entity_type": "Tx", "data": {"amount": 300}},
        ]
        batch = run(client.check_batch(items))

        assert isinstance(batch, BatchResult)
        assert batch.total == 3
        assert batch.accepted == 3
        assert batch.rejected == 0
        assert len(batch.results) == 3
        assert batch.mock is True
        assert all(r.mock for r in batch.results)
        assert all(r.passed for r in batch.results)

    def test_mock_pass_rate_zero_always_fails(self):
        """mock_pass_rate=0.0 means every check() call returns passed=False."""
        client = make_mock_client(mock_pass_rate=0.0)

        # Run multiple times to confirm it is deterministic at 0.0
        for _ in range(10):
            result = run(client.check("AgentResponse", SAMPLE_DATA))
            assert result.passed is False
            assert result.record_id is None
            assert result.fail_reason is not None
            assert result.failed_step == 9
            assert result.mock is True

    def test_entity_id_auto_generated(self):
        """check() generates a unique entity_id when none is provided."""
        client = make_mock_client()
        result1 = run(client.check("AgentResponse", SAMPLE_DATA))
        result2 = run(client.check("AgentResponse", SAMPLE_DATA))

        # Both should have non-empty entity IDs
        assert result1.entity_id
        assert result2.entity_id
        # They should be different (uuid4 generated)
        assert result1.entity_id != result2.entity_id

    def test_entity_id_preserved_when_provided(self):
        """check() preserves a caller-supplied entity_id."""
        client = make_mock_client()
        my_id = "my-stable-entity-id-123"
        result = run(client.check("AgentResponse", SAMPLE_DATA, entity_id=my_id))

        assert result.entity_id == my_id

    def test_batch_partial_pass(self):
        """With mixed pass rate, accepted + rejected == total."""
        import random
        random.seed(42)  # deterministic for the test
        client = make_mock_client(mock_pass_rate=0.5)
        items = [{"entity_type": "X", "data": {"v": i}} for i in range(20)]
        batch = run(client.check_batch(items))

        assert batch.total == 20
        assert batch.accepted + batch.rejected == batch.total
        assert len(batch.results) == 20

    def test_check_batch_auto_generates_entity_ids(self):
        """check_batch() auto-generates entity_id for items that omit it."""
        client = make_mock_client()
        items = [
            {"entity_type": "T", "data": {"x": 1}},  # no entity_id
            {"entity_type": "T", "data": {"x": 2}, "entity_id": "explicit-id"},
        ]
        batch = run(client.check_batch(items))

        assert batch.results[0].entity_id  # auto-generated, non-empty
        assert batch.results[1].entity_id == "explicit-id"


class TestErrorHandling:
    """Tests for TrustStateError and validation."""

    def test_trust_state_error_attributes(self):
        """TrustStateError carries message and status_code."""
        from truststate.exceptions import TrustStateError
        err = TrustStateError("something broke", 422)
        assert err.message == "something broke"
        assert err.status_code == 422
        assert "422" in repr(err)

    def test_compliant_decorator_raises_on_fail(self):
        """@compliant with on_fail='raise' raises TrustStateError when check fails."""
        from truststate import compliant
        from truststate.exceptions import TrustStateError

        client = make_mock_client(mock_pass_rate=0.0)

        @compliant(client, entity_type="Test", on_fail="raise")
        async def my_fn():
            return {"value": 1}

        with pytest.raises(TrustStateError):
            run(my_fn())

    def test_compliant_decorator_returns_none_on_fail(self):
        """@compliant with on_fail='return_none' returns None when check fails."""
        from truststate import compliant

        client = make_mock_client(mock_pass_rate=0.0)

        @compliant(client, entity_type="Test", on_fail="return_none")
        async def my_fn():
            return {"value": 1}

        result = run(my_fn())
        assert result is None

    def test_compliant_passes_through_value_on_success(self):
        """@compliant returns the original value when check passes."""
        from truststate import compliant

        client = make_mock_client(mock_pass_rate=1.0)
        expected = {"responseText": "hi", "confidenceScore": 0.9}

        @compliant(client, entity_type="Test", on_fail="raise")
        async def my_fn():
            return expected

        result = run(my_fn())
        assert result == expected
