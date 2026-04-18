import asyncio
import uuid

import pytest

from app.core.rate_limit import check_and_consume

pytestmark = pytest.mark.integration


async def test_allows_up_to_capacity() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    capacity = 3
    refill_rate = 0.1  # 1 token per 10s

    for _ in range(capacity):
        allowed, _ = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
        assert allowed is True


async def test_denies_over_capacity() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    capacity = 2
    refill_rate = 0.01  # very slow refill

    for _ in range(capacity):
        allowed, _ = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
        assert allowed is True

    allowed, retry = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
    assert allowed is False
    assert retry >= 1


async def test_refills_over_time() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    # 1 token capacity, refill 5 tokens/sec -> refill interval 200ms
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is True

    # Immediately denied
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is False

    # Wait for refill
    await asyncio.sleep(0.3)
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is True
