# TrustState Python SDK

[![PyPI version](https://img.shields.io/badge/pypi-0.1.0-blue)](https://github.com/MyreneBot/truststate-py)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Python SDK for **[TrustState](https://trustchainlabs.com)** — real-time compliance validation and immutable audit trails for AI agents and financial systems.

---

## Installation

```bash
# Not yet on PyPI — install directly from GitHub:
pip install git+https://github.com/MyreneBot/truststate-py.git

# Or clone and install locally:
git clone https://github.com/MyreneBot/truststate-py.git
pip install -e truststate-py/
```

---

## Quick Start

```python
import asyncio
from truststate import TrustStateClient

client = TrustStateClient(api_key="your-api-key")

async def main():
    result = await client.check(
        entity_type="AgentResponse",
        data={"responseText": "Portfolio rebalanced.", "confidenceScore": 0.92},
    )
    if result.passed:
        print(f"✅ Passed — record_id: {result.record_id}")
    else:
        print(f"❌ Failed — reason: {result.fail_reason} (step {result.failed_step})")

asyncio.run(main())
```

### Decorator Usage

Wrap any async function so its return value is automatically checked:

```python
from truststate import TrustStateClient, compliant

ts = TrustStateClient(api_key="your-api-key")

@compliant(ts, entity_type="AgentResponse", action="CREATE", on_fail="raise")
async def generate_response(customer_id: str) -> dict:
    return {
        "responseText": "Your account balance is RM 10,400.",
        "confidenceScore": 0.98,
    }

# Will raise TrustStateError if compliance check fails
response = await generate_response("CUST-001")
```

### Batch Submission

```python
results = await ts.check_batch([
    {"entity_type": "Transaction", "data": {"amount": 500, "currency": "MYR"}},
    {"entity_type": "Transaction", "data": {"amount": 99000, "currency": "MYR"}},
])
print(f"Accepted: {results.accepted}/{results.total}")
```

### FastAPI Middleware

```python
from fastapi import FastAPI
from truststate import TrustStateClient, TrustStateMiddleware

app = FastAPI()
client = TrustStateClient(api_key="your-api-key")
app.add_middleware(TrustStateMiddleware, client=client)

# Any request with X-Compliance-Entity-Type header will be validated.
# Failed checks return HTTP 422.
```

---

## Mock Mode

Mock mode lets you develop and test without an API connection. No network calls are made.

```python
client = TrustStateClient(
    api_key="any-value",
    mock=True,
    mock_pass_rate=0.8,  # 80% of checks pass; 20% fail
)

result = await client.check("AgentResponse", {"text": "hello"})
assert result.mock is True
```

**Use cases:**
- Unit tests (no API key needed)
- CI pipelines
- Local development without credentials
- Demonstrating the SDK offline

---

## API Reference

### `TrustStateClient(api_key, ...)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Your TrustState API key |
| `base_url` | `str` | `https://truststate-api.apps.trustchainlabs.com` | API base URL |
| `default_schema_version` | `str` | `"1.0"` | Schema version for submissions |
| `default_actor_id` | `str` | `""` | Actor ID for audit trail |
| `mock` | `bool` | `False` | Enable mock mode |
| `mock_pass_rate` | `float` | `1.0` | Probability of passing in mock mode |
| `timeout` | `int` | `30` | HTTP timeout in seconds |

### `await client.check(entity_type, data, ...)`

Submit a single record for compliance validation.

Returns: `ComplianceResult`

### `await client.check_batch(items, ...)`

Submit multiple records in one API call.

Returns: `BatchResult`

### `await client.verify(record_id, bearer_token)`

Retrieve an immutable compliance record from the ledger.

Returns: `dict`

---

## ComplianceResult Fields

| Field | Type | Description |
|---|---|---|
| `passed` | `bool` | True if all checks passed |
| `record_id` | `Optional[str]` | Immutable ledger ID (set only when passed) |
| `request_id` | `str` | Unique API request ID |
| `entity_id` | `str` | The entity identifier |
| `fail_reason` | `Optional[str]` | Human-readable failure reason |
| `failed_step` | `Optional[int]` | Step that failed (8=schema, 9=policy) |
| `mock` | `bool` | True when result is synthetic (mock mode) |

---

## API Compatibility

| SDK Version | TrustState API |
|---|---|
| 0.1.x | v1 |

---

## Platform

Built for [TrustState](https://trustchainlabs.com) by [TrustChain Labs](https://trustchainlabs.com).

TrustState provides real-time compliance validation and immutable audit trails for AI agents, financial transactions, and regulated workflows.
