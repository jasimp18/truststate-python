# TrustState Python SDK

[![PyPI version](https://img.shields.io/pypi/v/truststate.svg)](https://pypi.org/project/truststate/)
[![Python](https://img.shields.io/pypi/pyversions/truststate.svg)](https://pypi.org/project/truststate/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Python SDK for the [TrustState](https://truststate.apps.trustchainlabs.com) compliance API — validate, audit, and enforce compliance rules on any entity or data record. Built for financial services, AI governance, and regulated industries.

## Install

```bash
pip install truststate
```

Requires Python 3.9+.

## Quickstart

```python
import asyncio
from truststate import TrustStateClient

client = TrustStateClient(
    api_key="ts_your_api_key",
    default_actor_id="my-service-001",  # must be registered in TrustState dashboard
)

async def main():
    result = await client.check(
        entity_type="SukukBond",
        data={
            "id": "BOND-001",
            "issuerId": "ISS-001",
            "currency": "MYR",
            "faceValue": 5_000_000,
            "maturityDate": "2030-06-01",
            "status": "DRAFT",
        },
    )

    if result.passed:
        print(f"✅ Passed — record ID: {result.record_id}")
    else:
        print(f"❌ Failed — {result.fail_reason} (step {result.failed_step})")

asyncio.run(main())
```

## Batch Writes

Submit multiple records in a single API call. Useful for feed-based pipelines.

```python
result = await client.check_batch(
    items=[
        {"entity_type": "SukukBond", "data": {"id": "BOND-001", ...}},
        {"entity_type": "SukukBond", "data": {"id": "BOND-002", ...}},
        {"entity_type": "SukukBond", "data": {"id": "BOND-003", ...}},
    ],
    feed_label="core-banking-feed",       # echoed on every item result
    default_actor_id="my-service-001",    # must be registered in TrustState dashboard
)

print(f"Accepted: {result.accepted}/{result.total}")
for item in result.results:
    print(f"  {item.entity_id}: {'✅' if item.passed else '❌'} {item.feed_label}")
```

## BYOP Evidence (Oracle Data)

Attach oracle evidence to compliance checks — FX rates, KYC status, credit scores, sanctions screening.

```python
# Fetch evidence from registered oracle providers
fx    = await client.fetch_fx_rate("MYR", "USD")
kyc   = await client.fetch_kyc_status("actor-jasim")
score = await client.fetch_credit_score("actor-jasim")

# Submit with evidence attached
result = await client.check_with_evidence(
    entity_type="SukukBond",
    data={"id": "BOND-001", "issuerId": "ISS-001", "currency": "MYR", "faceValue": 5_000_000},
    evidence=[fx, kyc, score],
)
```

## Mock Mode

Test without making any API calls. Useful for unit tests and local development.

```python
client = TrustStateClient(
    api_key="any",
    mock=True,
    mock_pass_rate=0.8,   # 80% of checks will pass
)

result = await client.check("SukukBond", {"id": "TEST-001", ...})
print(result.mock)   # True
```

## Django / FastAPI Middleware

Automatically validate every incoming request body against TrustState policies.

```python
# FastAPI
from truststate import TrustStateMiddleware

app.add_middleware(
    TrustStateMiddleware,
    api_key="ts_your_api_key",
    entity_type="AgentResponse",
)

# Django
MIDDLEWARE = [
    "truststate.middleware.TrustStateMiddleware",
    ...
]
TRUSTSTATE_API_KEY = "ts_your_api_key"
TRUSTSTATE_ENTITY_TYPE = "AgentResponse"
```

## `@compliant` Decorator

Wrap any async function to automatically submit its return value for compliance checking.

```python
from truststate import compliant, TrustStateClient

client = TrustStateClient(api_key="ts_your_api_key")

@compliant(client=client, entity_type="AgentResponse")
async def generate_response(prompt: str) -> dict:
    return {"text": "Hello!", "score": 0.95}

result = await generate_response("What is TrustState?")
# result is a ComplianceResult — .passed, .record_id, etc.
```

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Your TrustState API key |
| `base_url` | `str` | production URL | Override the API base URL |
| `default_schema_version` | `str \| None` | `None` | Schema version (auto-resolved if omitted) |
| `default_actor_id` | `str` | **required** | Registered Data Source ID — must match a source registered in the TrustState dashboard. All writes are rejected without a valid Source ID. |
| `mock` | `bool` | `False` | Enable mock mode (no HTTP calls) |
| `mock_pass_rate` | `float` | `1.0` | Pass probability in mock mode (0.0–1.0) |
| `timeout` | `int` | `30` | HTTP timeout in seconds |


## Data Sources (Required)

Every write must come from a **registered Data Source**. Register sources in the TrustState dashboard under **Manage → Data Sources**, then use the Source ID as `actor_id`.

```python
# Register "my-service-001" in the dashboard first, then:
client = TrustStateClient(
    api_key="ts_your_api_key",
    default_actor_id="my-service-001",  # applies to all check() / check_batch() calls
)

# Or pass per-call:
result = await client.check(
    entity_type="KYCRecord",
    data=data,
    actor_id="my-service-001",
)
```

If `actor_id` is missing, the SDK raises `TrustStateError` before sending any request.
If `actor_id` is not registered, the API returns `403 UNKNOWN_SOURCE`.

## API Reference

### `check(entity_type, data, *, action, entity_id, schema_version, actor_id)`

Submit a single record for compliance checking.

Returns: `ComplianceResult`

### `check_batch(items, *, default_schema_version, default_actor_id, feed_label)`

Submit up to 500 records in a single call.

Returns: `BatchResult`

### `check_with_evidence(entity_type, data, evidence, *, action, entity_id, schema_version, actor_id)`

Submit a record with oracle evidence attached.

Returns: `ComplianceResult`

### `fetch_fx_rate(from_currency, to_currency, *, provider_id, max_age_seconds)`
### `fetch_kyc_status(subject_id, *, provider_id, max_age_seconds)`
### `fetch_credit_score(subject_id, *, provider_id, max_age_seconds)`
### `fetch_sanctions(subject_id, *, provider_id, max_age_seconds)`

Fetch oracle evidence items from registered providers.

Returns: `EvidenceItem`

### `verify(record_id, bearer_token)`

Retrieve an immutable compliance record from the ledger.

Returns: `dict`

## ComplianceResult

| Field | Type | Description |
|---|---|---|
| `passed` | `bool` | True if all checks passed |
| `record_id` | `str \| None` | Immutable ledger record ID (only when passed) |
| `request_id` | `str` | Unique API request ID |
| `entity_id` | `str` | Entity ID that was submitted |
| `fail_reason` | `str \| None` | Human-readable failure reason |
| `failed_step` | `int \| None` | Step that failed (8=schema, 9=policy) |
| `feed_label` | `str \| None` | Feed label from batch request |
| `mock` | `bool` | True if synthesised in mock mode |

## Requirements

- Python 3.9+
- `httpx>=0.27`

## License

MIT © Trustchain Labs
