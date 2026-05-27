"""Async exponential-backoff retry helper for OpenAI calls."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Tuple, Type, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

DEFAULT_DELAYS: Tuple[float, ...] = (2.0, 4.0, 8.0)


def _default_retryable_exceptions() -> Tuple[Type[BaseException], ...]:
    """Return the exception types we retry on, importing lazily so that the
    `openai` package remains an optional runtime dependency."""
    exceptions: list[Type[BaseException]] = []
    try:
        from openai import (  # type: ignore
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )

        exceptions.extend(
            [APIConnectionError, APITimeoutError, InternalServerError, RateLimitError]
        )
    except Exception:  # pragma: no cover - openai always installed in practice
        pass
    exceptions.extend([ConnectionError, TimeoutError])
    return tuple(exceptions)


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    delays: Tuple[float, ...] = DEFAULT_DELAYS,
    retry_on: Tuple[Type[BaseException], ...] | None = None,
    label: str = "openai",
) -> T:
    """Call `func()` with exponential backoff (default 2s/4s/8s, 3 retries)."""
    retry_on = retry_on or _default_retryable_exceptions()
    last_exc: BaseException | None = None
    for attempt in range(len(delays) + 1):
        try:
            return await func()
        except retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt >= len(delays):
                break
            delay = delays[attempt]
            logger.warning(
                "%s call failed (attempt %s/%s): %s — retrying in %ss",
                label,
                attempt + 1,
                len(delays) + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
