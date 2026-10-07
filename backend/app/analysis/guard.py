"""A time limit around anything that calls a model.

The app has one failure it cannot recover from on its own: a provider that
neither answers nor fails. A request waiting on it is held open for ever, a
background task never finishes, and with a few of those the app looks dead when
only the model is - which is what forced a restart every time usage ran out.

So every call through an analyzer or a scanner gets a ceiling. Past it the call
is abandoned and reported as a failure, which the callers already know how to
survive: a debrief records the error and keeps the question, a chat says it
could not answer, a scan tells the student to type it in.

Written as a proxy rather than a decorator on each method so that adding a
method to the protocol cannot quietly add an unguarded path.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .base import AnalysisFailed


class Guarded:
    """Wraps a provider; every awaitable attribute comes back time-limited."""

    def __init__(self, inner: Any, seconds: float) -> None:
        self._inner = inner
        self._seconds = seconds

    @property
    def name(self) -> str:
        return getattr(self._inner, "name", "unknown")

    def __getattr__(self, item: str) -> Any:
        attribute = getattr(self._inner, item)
        if not callable(attribute):
            return attribute

        async def limited(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(attribute(*args, **kwargs), self._seconds)
            except TimeoutError as exc:
                raise AnalysisFailed(
                    f"the model did not answer within {self._seconds:.0f}s"
                ) from exc

        return limited
