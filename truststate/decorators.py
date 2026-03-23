"""Decorators for automatic TrustState compliance checking.

Usage::

    from truststate import TrustStateClient, compliant

    ts = TrustStateClient(api_key="your-key")

    @compliant(ts, entity_type="AgentResponse", action="CREATE")
    async def generate_response(customer_id: str) -> dict:
        return {"responseText": "Hello!", "confidenceScore": 0.95}
"""

from __future__ import annotations

import functools
import inspect
import logging
import warnings
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def compliant(
    client: Any,  # TrustStateClient — avoid circular import
    entity_type: str,
    action: str = "CREATE",
    data_fn: Optional[Callable[[Any], dict]] = None,
    on_fail: str = "raise",
) -> Callable:
    """Decorator that submits the wrapped function's return value to TrustState.

    The decorated function runs first; its return value is then submitted for
    compliance validation. Depending on ``on_fail``, a failed check either raises
    an exception, logs a warning, or returns None.

    Args:
        client: A TrustStateClient instance.
        entity_type: The entity type to register with TrustState.
        action: The action string — "CREATE", "UPDATE", or "DELETE".
        data_fn: Optional mapping function: ``data_fn(return_value) -> dict``.
            If omitted, the return value must already be a dict (or have ``__dict__``).
        on_fail: Behaviour when compliance check fails:
            - ``"raise"`` — raise TrustStateError (default).
            - ``"warn"``  — log a warning and return the original value anyway.
            - ``"return_none"`` — silently return None.

    Returns:
        Decorated async function.

    Raises:
        ValueError: If on_fail is not a recognised value.
        TrustStateError: (when on_fail="raise") if the compliance check fails.
    """
    if on_fail not in ("raise", "warn", "return_none"):
        raise ValueError(f"on_fail must be 'raise', 'warn', or 'return_none'; got {on_fail!r}")

    def decorator(func: Callable) -> Callable:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"@compliant requires an async function; {func.__name__} is not async."
            )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Run the original function
            result = await func(*args, **kwargs)

            # Convert result to dict for submission
            if data_fn is not None:
                data = data_fn(result)
            elif isinstance(result, dict):
                data = result
            elif hasattr(result, "__dict__"):
                data = result.__dict__
            else:
                raise TypeError(
                    f"Cannot extract dict from return value of {func.__name__}. "
                    "Provide a data_fn or return a dict/dataclass."
                )

            # Submit to TrustState
            compliance = await client.check(
                entity_type=entity_type,
                data=data,
                action=action,
            )

            if compliance.passed:
                return result

            # Handle failure
            if on_fail == "raise":
                from .exceptions import TrustStateError
                raise TrustStateError(
                    f"Compliance check failed for {entity_type}: "
                    f"{compliance.fail_reason} (step {compliance.failed_step})"
                )
            elif on_fail == "warn":
                warnings.warn(
                    f"TrustState compliance failed for {entity_type} "
                    f"(entity_id={compliance.entity_id}): {compliance.fail_reason}",
                    stacklevel=2,
                )
                return result
            else:  # return_none
                logger.debug(
                    "Compliance failed for %s entity_id=%s reason=%s — returning None",
                    entity_type,
                    compliance.entity_id,
                    compliance.fail_reason,
                )
                return None

        return wrapper

    return decorator
