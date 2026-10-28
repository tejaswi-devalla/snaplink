from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# One atomic operation per request; counters are shared across all instances via Redis.
REDIS_COUNTER_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def rate_limit(kind: str, *, fail_closed: bool = True) -> Callable[..., Awaitable[None]]:
    async def dependency(request: Request) -> None:
        settings = request.app.state.settings
        limit = int(getattr(settings, f"{kind}_limit"))
        window = int(getattr(settings, f"{kind}_window_seconds"))
        client_ip = request.client.host if request.client else "unknown"
        # Hash identifiers to avoid keeping raw client IPs in Redis keys.
        client_key = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:32]
        now = time.time()
        bucket = int(now // window)
        key = f"snaplink:rate:{kind}:{client_key}:{bucket}"
        count: int

        redis_client = request.app.state.redis
        if redis_client is not None:
            try:
                count = int(await redis_client.eval(REDIS_COUNTER_SCRIPT, 1, key, window + 1))
            except Exception as exc:  # Redis outage policy depends on the endpoint.
                logger.warning("Rate-limit backend unavailable for %s: %s", kind, type(exc).__name__)
                if fail_closed:
                    raise HTTPException(status_code=503, detail="Request protection is temporarily unavailable") from exc
                return
        else:
            if settings.environment == "production":
                raise HTTPException(status_code=503, detail="Request protection is temporarily unavailable")
            count = await _local_counter(request, key, now, window)

        if count > limit:
            retry_after = max(1, window - (int(now) % window))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


async def _local_counter(request: Request, key: str, now: float, window: int) -> int:
    """Process-local fallback for development and tests only."""
    counters: dict[str, tuple[int, float]] = request.app.state.local_rate_limits
    lock: asyncio.Lock = request.app.state.local_rate_limits_lock
    async with lock:
        current = counters.get(key)
        if current is None or current[1] <= now:
            counters[key] = (1, now + window)
            count = 1
        else:
            count = current[0] + 1
            counters[key] = (count, current[1])
        # Bound the fallback map so arbitrary client identifiers cannot grow it forever.
        if len(counters) > 10_000:
            for counter_key, (_, expiry) in list(counters.items()):
                if expiry <= now:
                    counters.pop(counter_key, None)
        return count
