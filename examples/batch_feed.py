# Run: pip install truststate && python examples/batch_feed.py
#
# CIMB-style batch ingestion demo.
# Simulates a financial institution submitting 10 transactions in a single
# batch call for compliance validation before they are processed downstream.
#
# Runs in mock mode automatically when TRUSTSTATE_API_KEY is not set.

from __future__ import annotations

import asyncio
import os
import uuid

from truststate import TrustStateClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.getenv("TRUSTSTATE_API_KEY", "")
BASE_URL = os.getenv("TRUSTSTATE_BASE_URL", "https://truststate-api.apps.trustchainlabs.com")
USE_MOCK = not bool(API_KEY)

if USE_MOCK:
    print("⚠️  TRUSTSTATE_API_KEY not set — running in MOCK mode (no network calls).\n")

# ---------------------------------------------------------------------------
# Sample transaction batch (CIMB-style)
# ---------------------------------------------------------------------------
TRANSACTIONS = [
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-001",
            "toAccount": "MY-ACC-099",
            "amount": 1500.00,
            "currency": "MYR",
            "channel": "MOBILE_APP",
            "category": "TRANSFER",
            "riskScore": 0.12,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-002",
            "toAccount": "VENDOR-567",
            "amount": 299.99,
            "currency": "MYR",
            "channel": "ONLINE_BANKING",
            "category": "BILL_PAYMENT",
            "riskScore": 0.05,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-003",
            "toAccount": "INTL-BANK-AU",
            "amount": 50000.00,
            "currency": "MYR",
            "channel": "BRANCH",
            "category": "INTERNATIONAL_TRANSFER",
            "riskScore": 0.78,  # high risk — likely to fail policy
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-004",
            "toAccount": "MY-ACC-110",
            "amount": 800.00,
            "currency": "MYR",
            "channel": "ATM",
            "category": "CASH_WITHDRAWAL",
            "riskScore": 0.09,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-005",
            "toAccount": "E-WALLET-GXS",
            "amount": 150.00,
            "currency": "MYR",
            "channel": "MOBILE_APP",
            "category": "WALLET_TOP_UP",
            "riskScore": 0.03,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-006",
            "toAccount": "MY-ACC-006",
            "amount": 0.01,
            "currency": "MYR",
            "channel": "SYSTEM",
            "category": "INTEREST_CREDIT",
            "riskScore": 0.00,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "UNKNOWN",  # suspicious — missing KYC
            "toAccount": "MY-ACC-007",
            "amount": 9900.00,
            "currency": "MYR",
            "channel": "ONLINE_BANKING",
            "category": "TRANSFER",
            "riskScore": 0.91,  # very high risk
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-008",
            "toAccount": "MERCHANT-MCM",
            "amount": 4200.00,
            "currency": "MYR",
            "channel": "POS",
            "category": "PURCHASE",
            "riskScore": 0.14,
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-009",
            "toAccount": "CRYPTO-EXCHANGE",
            "amount": 25000.00,
            "currency": "MYR",
            "channel": "ONLINE_BANKING",
            "category": "CRYPTO_PURCHASE",
            "riskScore": 0.67,  # elevated risk
        },
    },
    {
        "entity_type": "FinancialTransaction",
        "action": "CREATE",
        "data": {
            "transactionId": f"TXN-{str(uuid.uuid4())[:8].upper()}",
            "fromAccount": "MY-ACC-010",
            "toAccount": "GOVT-LHDN",
            "amount": 12500.00,
            "currency": "MYR",
            "channel": "ONLINE_BANKING",
            "category": "TAX_PAYMENT",
            "riskScore": 0.02,
        },
    },
]


async def run_batch_demo() -> None:
    client = TrustStateClient(
        api_key=API_KEY or "mock-key",
        base_url=BASE_URL,
        default_schema_version="1.0",
        default_actor_id="CIMB-BATCH-PROCESSOR",
        mock=USE_MOCK,
        mock_pass_rate=0.7,  # Simulate ~70% pass rate for demo
    )

    print("=" * 72)
    print("  TrustState Batch Ingestion Demo — CIMB-style Transactions")
    print("=" * 72)
    print(f"  Mode       : {'MOCK' if USE_MOCK else 'LIVE'}")
    print(f"  Batch size : {len(TRANSACTIONS)} transactions")
    print("=" * 72)
    print()

    batch_result = await client.check_batch(
        items=TRANSACTIONS,
        default_schema_version="1.0",
        default_actor_id="CIMB-BATCH-PROCESSOR",
    )

    # Summary
    print(f"  Batch ID  : {batch_result.batch_id}")
    print(f"  Total     : {batch_result.total}")
    print(f"  ✅ Accepted : {batch_result.accepted}")
    print(f"  ❌ Rejected : {batch_result.rejected}")
    print()

    # Per-item results
    print(f"{'#':<3} {'Entity ID':<38} {'Status':<8} {'Record / Reason'}")
    print("-" * 72)

    for idx, result in enumerate(batch_result.results, start=1):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        entity_id_short = result.entity_id[:36]

        if result.passed:
            detail = f"record_id={result.record_id}"
        else:
            detail = f"{result.fail_reason}"

        print(f"{idx:<3} {entity_id_short:<38} {status:<8} {detail}")

    print()
    acceptance_rate = (batch_result.accepted / batch_result.total * 100) if batch_result.total else 0
    print(f"  Acceptance rate: {acceptance_rate:.0f}%")
    print()

    if batch_result.rejected > 0:
        print("⚠️  Rejected transactions require manual review before processing.")
    else:
        print("✅ All transactions cleared for processing.")


if __name__ == "__main__":
    asyncio.run(run_batch_demo())
