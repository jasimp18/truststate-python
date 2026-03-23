"""
TrustState Python SDK
~~~~~~~~~~~~~~~~~~~~~

A Python SDK for TrustState compliance validation.

Basic usage::

    import asyncio
    from truststate import TrustStateClient

    client = TrustStateClient(api_key="your-api-key")

    async def main():
        result = await client.check(
            entity_type="AgentResponse",
            data={"responseText": "Hello!", "confidenceScore": 0.95}
        )
        print(result.passed, result.record_id)

    asyncio.run(main())
"""

from .client import TrustStateClient
from .types import ComplianceResult, BatchResult
from .decorators import compliant
from .middleware import TrustStateMiddleware
from .exceptions import TrustStateError

__all__ = [
    "TrustStateClient",
    "ComplianceResult",
    "BatchResult",
    "compliant",
    "TrustStateMiddleware",
    "TrustStateError",
]

__version__ = "0.1.0"
