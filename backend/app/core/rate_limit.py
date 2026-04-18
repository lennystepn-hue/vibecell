"""Token-bucket rate limiter backed by Redis.

Each unique `key` gets an independent bucket. The Lua script below runs
atomically on the server: compute elapsed since last refill, add tokens
capped at capacity, deduct 1 if any remain, otherwise return (0, wait).
"""
from __future__ import annotations

import math

from app.core.redis import get_redis

# KEYS[1] = bucket key
# ARGV[1] = capacity (max tokens, float as string)
# ARGV[2] = refill_rate (tokens/sec, float as string)
# ARGV[3] = now_ms (integer milliseconds since epoch)
# ARGV[4] = ttl_ms (integer, expiry of the key)
#
# Returns [allowed (0|1), retry_after_ms (integer)]
_LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "last_ms")
local tokens = tonumber(data[1])
local last_ms = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  last_ms = now_ms
end

local elapsed = (now_ms - last_ms) / 1000.0
if elapsed < 0 then elapsed = 0 end
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
local retry_after_ms = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
else
  -- how long until we have 1 token?
  retry_after_ms = math.ceil((1 - tokens) / refill * 1000)
end

redis.call("HMSET", key, "tokens", tostring(tokens), "last_ms", tostring(now_ms))
redis.call("PEXPIRE", key, ttl_ms)
return {allowed, retry_after_ms}
"""


async def check_and_consume(
    key: str,
    *,
    capacity: int,
    refill_rate: float,
) -> tuple[bool, int]:
    """Atomically consume 1 token from `key`'s bucket.

    Args:
      key: Redis key identifying the bucket (caller should namespace).
      capacity: maximum tokens in bucket.
      refill_rate: tokens per second.

    Returns:
      (allowed, retry_after_seconds). retry_after is 0 when allowed, else >= 1.
    """
    import time

    redis = await get_redis()
    now_ms = int(time.time() * 1000)
    # Key expires 2x the time to fully refill, so stale buckets don't linger.
    ttl_ms = int(max(60_000, (capacity / max(refill_rate, 0.001)) * 2_000))

    result = await redis.eval(  # type: ignore[no-untyped-call]
        _LUA_TOKEN_BUCKET,
        1,
        key,
        str(capacity),
        str(refill_rate),
        str(now_ms),
        str(ttl_ms),
    )
    allowed_i, retry_ms = result
    retry_s = math.ceil(int(retry_ms) / 1000) if int(retry_ms) > 0 else 0
    return bool(int(allowed_i)), retry_s
