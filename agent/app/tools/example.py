"""Example tools — delete these and drop in your own.

They exist to demonstrate the two shapes of tool this template supports:

  - `compute` is a pure function tool: it takes args, returns a JSON-able dict.
    This is the common case — call an API, do some math, look something up.
  - `sample_series` shows the chart pipeline: it stashes a Plotly trace in the
    ToolContext under a `ref` (via `ctx.put_traces`) and returns that ref. The
    model then passes the ref to `make_chart` (in emit.py) to render it, so the
    large data array is sent to the browser once as a `data` event rather than
    inlined into the model context.

Each module exports `*_TOOLS` (OpenAI function schemas) and `*_HANDLERS`
(`async (ctx, args) -> dict`), aggregated in `tools/__init__.py`.
"""
from __future__ import annotations

import math
import uuid
from typing import Any

from .context import ToolContext


async def compute(ctx: ToolContext, args: dict) -> dict:
    """A trivial calculator, to show the request/response shape of a tool."""
    op = args.get("operation")
    a = float(args.get("a", 0))
    b = float(args.get("b", 0))
    try:
        if op == "add":
            result = a + b
        elif op == "subtract":
            result = a - b
        elif op == "multiply":
            result = a * b
        elif op == "divide":
            if b == 0:
                return {"error": "division by zero"}
            result = a / b
        elif op == "power":
            result = a ** b
        else:
            return {"error": f"unknown operation {op!r} (add|subtract|multiply|divide|power)"}
    except (ValueError, OverflowError) as e:
        return {"error": f"compute failed: {e}"}
    return {"operation": op, "a": a, "b": b, "result": result}


async def sample_series(ctx: ToolContext, args: dict) -> dict:
    """Generate a small deterministic series and stash it as a chart trace.

    Returns a `ref` the model hands to `make_chart`. Shape mirrors what a real
    data tool (a price history, a metrics timeseries) would do.
    """
    points = max(2, min(int(args.get("points", 50)), 1000))
    kind = args.get("kind", "sine")
    xs = list(range(points))
    if kind == "linear":
        ys = [float(x) for x in xs]
    elif kind == "square":
        ys = [float(x * x) for x in xs]
    else:  # sine
        ys = [round(math.sin(x / 4.0), 4) for x in xs]

    ref = f"series://{kind}/{uuid.uuid4().hex[:8]}"
    trace = {"x": xs, "y": ys, "type": "scatter", "mode": "lines", "name": kind}
    await ctx.put_traces(ref, [trace])
    return {"ref": ref, "kind": kind, "n_points": points}


EXAMPLE_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "compute",
            "description": "Evaluate a simple arithmetic operation on two numbers. Prefer this over doing math in your head so results are reproducible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide", "power"],
                    },
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["operation", "a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sample_series",
            "description": "Generate a sample numeric series and return a chart `ref`. Pass the ref to make_chart to render it. Demonstrates the data-ref → chart pipeline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {"type": "integer", "description": "Number of points (2–1000)."},
                    "kind": {"type": "string", "enum": ["sine", "linear", "square"]},
                },
                "required": [],
            },
        },
    },
]

EXAMPLE_HANDLERS: dict[str, Any] = {
    "compute": compute,
    "sample_series": sample_series,
}
