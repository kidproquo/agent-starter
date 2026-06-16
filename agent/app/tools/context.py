from __future__ import annotations

from typing import Any, Awaitable, Callable


class ToolContext:
    """Shared state threaded through every tool handler.

    - `emit` pushes SSE events (render blocks, chart data) to the response stream.
    - `data_cache` holds Plotly trace lists keyed by ref, so chart blocks can carry a
      lightweight `dataRef` instead of inlining large data arrays into the model context.
    - `request` carries the originating PromptRequest context (attachment text, etc.).
    - `user` is the authenticated UserContext (or None in tests); user-management
      tools gate on `user.is_admin`.
    """

    def __init__(
        self,
        emit: Callable[[str, Any], Awaitable[None]],
        request: Any = None,
        user: Any = None,
    ):
        self.emit = emit
        self.request = request
        self.user = user
        self.data_cache: dict[str, list[dict]] = {}

    async def put_traces(self, ref: str, traces: list[dict]) -> None:
        self.data_cache[ref] = traces
        await self.emit("data", {"ref": ref, "traces": traces})
