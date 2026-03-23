"""FastAPI middleware for automatic TrustState compliance checking.

Usage::

    from fastapi import FastAPI
    from truststate import TrustStateClient, TrustStateMiddleware

    app = FastAPI()
    client = TrustStateClient(api_key="your-key")
    app.add_middleware(TrustStateMiddleware, client=client)

Any request that includes the ``X-Compliance-Entity-Type`` header will have its
body submitted to TrustState before being passed to the route handler.
A failed compliance check returns HTTP 422.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.types import ASGIApp

    _STARLETTE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STARLETTE_AVAILABLE = False
    BaseHTTPMiddleware = object  # type: ignore[misc,assignment]


class TrustStateMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    """FastAPI/Starlette middleware that gates requests on TrustState compliance.

    Inspects two custom headers on every incoming request:

    - ``X-Compliance-Entity-Type``: The TrustState entity type to validate against.
    - ``X-Compliance-Action``: The action string (default "CREATE").

    If ``X-Compliance-Entity-Type`` is present, the raw request body is parsed as
    JSON and submitted to TrustState. The request is allowed through only if the
    compliance check passes; otherwise a 422 response is returned immediately.

    Args:
        app: The ASGI application to wrap.
        client: A TrustStateClient instance.
        entity_id_header: Optional request header that carries a stable entity ID.
            If absent, one is auto-generated per request.
    """

    def __init__(
        self,
        app: Any,
        client: Any,  # TrustStateClient — avoid circular import
        entity_id_header: str = "X-Compliance-Entity-Id",
    ) -> None:
        if not _STARLETTE_AVAILABLE:
            raise ImportError(
                "starlette is required for TrustStateMiddleware. "
                "Install it with: pip install starlette"
            )
        super().__init__(app)
        self._client = client
        self._entity_id_header = entity_id_header

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        entity_type: Optional[str] = request.headers.get("X-Compliance-Entity-Type")

        # Pass through if the compliance header is absent
        if not entity_type:
            return await call_next(request)

        action = request.headers.get("X-Compliance-Action", "CREATE")
        entity_id = request.headers.get(self._entity_id_header)

        # Read and parse the request body
        try:
            raw_body = await request.body()
            data = json.loads(raw_body) if raw_body else {}
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("TrustStateMiddleware: failed to parse request body: %s", exc)
            return JSONResponse(
                {"error": "Invalid JSON body for compliance check"},
                status_code=400,
            )

        # Run compliance check
        try:
            result = await self._client.check(
                entity_type=entity_type,
                data=data,
                action=action,
                entity_id=entity_id or None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("TrustStateMiddleware: compliance check error: %s", exc)
            return JSONResponse(
                {"error": "Compliance service unavailable", "detail": str(exc)},
                status_code=503,
            )

        if not result.passed:
            logger.info(
                "TrustStateMiddleware: blocked request — entity_type=%s reason=%s",
                entity_type,
                result.fail_reason,
            )
            return JSONResponse(
                {
                    "error": "Compliance check failed",
                    "fail_reason": result.fail_reason,
                    "failed_step": result.failed_step,
                    "entity_id": result.entity_id,
                },
                status_code=422,
            )

        # Attach the record ID so downstream handlers can use it
        response = await call_next(request)
        if result.record_id:
            response.headers["X-Compliance-Record-Id"] = result.record_id
        return response
