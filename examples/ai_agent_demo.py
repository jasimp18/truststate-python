# Run: pip install truststate && python examples/ai_agent_demo.py
#
# This demo simulates an AI agent that generates responses and submits each one
# to TrustState for compliance validation before delivering to the end user.
#
# If API_KEY is not set in the environment, the demo automatically runs in
# mock mode — no network calls, fully self-contained.

from __future__ import annotations

import asyncio
import os

from truststate import TrustStateClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.getenv("TRUSTSTATE_API_KEY", "")
BASE_URL = os.getenv("TRUSTSTATE_BASE_URL", "https://truststate-api.apps.trustchainlabs.com")

# Automatically enable mock mode when no API key is available
USE_MOCK = not bool(API_KEY)

if USE_MOCK:
    print("⚠️  TRUSTSTATE_API_KEY not set — running in MOCK mode (no network calls).\n")

# ---------------------------------------------------------------------------
# Sample agent responses
# 3 are designed to be compliant, 2 are non-compliant (would fail policy checks)
# ---------------------------------------------------------------------------
AGENT_RESPONSES = [
    # --- Compliant ---
    {
        "name": "Balanced investment advice",
        "payload": {
            "responseText": (
                "Based on your risk profile, a balanced portfolio with 60% equities "
                "and 40% bonds is recommended. Past performance is not indicative of "
                "future results. Please consult a licensed financial advisor."
            ),
            "confidenceScore": 0.92,
            "hasDisclaimer": True,
            "category": "INVESTMENT_ADVICE",
        },
    },
    {
        "name": "Loan eligibility check",
        "payload": {
            "responseText": (
                "Your preliminary eligibility score is 720. This is an indicative "
                "assessment only. Final approval is subject to full credit evaluation."
            ),
            "confidenceScore": 0.88,
            "hasDisclaimer": True,
            "category": "CREDIT_ASSESSMENT",
        },
    },
    {
        "name": "Transaction summary",
        "payload": {
            "responseText": "Your last 5 transactions total RM 4,230.50.",
            "confidenceScore": 0.99,
            "hasDisclaimer": False,
            "category": "ACCOUNT_INFO",
        },
    },
    # --- Non-compliant: low confidence score ---
    {
        "name": "Uncertain market prediction (low confidence)",
        "payload": {
            "responseText": "The stock will definitely rise 20% next quarter.",
            "confidenceScore": 0.31,  # below acceptable threshold
            "hasDisclaimer": False,
            "category": "MARKET_PREDICTION",
        },
    },
    # --- Non-compliant: missing required disclaimer ---
    {
        "name": "Insurance recommendation without disclaimer",
        "payload": {
            "responseText": "I recommend upgrading to the Premium Life plan — it covers everything.",
            "confidenceScore": 0.78,
            "hasDisclaimer": False,  # required for insurance category
            "category": "INSURANCE_RECOMMENDATION",
        },
    },
]

# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

async def run_demo() -> None:
    client = TrustStateClient(
        api_key=API_KEY or "mock-key",
        base_url=BASE_URL,
        mock=USE_MOCK,
        # In mock mode: simulate that 3/5 pass (matches our designed compliant ones)
        mock_pass_rate=0.6,
    )

    print("=" * 72)
    print("  TrustState AI Agent Compliance Demo")
    print("=" * 72)
    print(f"  Mode : {'MOCK (synthetic results)' if USE_MOCK else 'LIVE (API calls)'}")
    print(f"  API  : {BASE_URL}")
    print("=" * 72)
    print()

    # Table header
    print(
        f"{'#':<3} {'Name':<42} {'Status':<8} {'Step':<6} {'Record / Reason'}"
    )
    print("-" * 72)

    for idx, response in enumerate(AGENT_RESPONSES, start=1):
        result = await client.check(
            entity_type="AgentResponse",
            data=response["payload"],
            action="CREATE",
        )

        status = "✅ PASS" if result.passed else "❌ FAIL"
        step = str(result.failed_step) if result.failed_step else "—"

        if result.passed:
            detail = f"record_id={result.record_id}"
        else:
            detail = f"{result.fail_reason}"

        name_display = response["name"][:41]
        print(f"{idx:<3} {name_display:<42} {status:<8} {step:<6} {detail}")

    print()

    # Audit trail for passed records
    print("📋 Audit trail URLs (passed records):")
    for idx, response in enumerate(AGENT_RESPONSES, start=1):
        result = await client.check(
            entity_type="AgentResponse",
            data=response["payload"],
            action="CREATE",
        )
        if result.passed and result.record_id:
            url = f"{BASE_URL}/v1/records/{result.record_id}"
            print(f"  [{idx}] {url}")

    print()
    print("Done. In production, passed record_ids are immutable compliance evidence.")
    print("Use client.verify(record_id, bearer_token) to retrieve a full audit record.")


if __name__ == "__main__":
    asyncio.run(run_demo())
