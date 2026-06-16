"""Emit tools — the agent assembles its user-visible answer by calling these, which
push render blocks onto the SSE stream. Plain model text is treated as scratchpad
reasoning; only emitted blocks appear in the response body.
"""

from __future__ import annotations

from typing import Any

from .context import ToolContext


async def make_markdown(ctx: ToolContext, args: dict) -> dict:
    await ctx.emit("block", {"type": "markdown", "content": args["content"]})
    return {"emitted": "markdown", "chars": len(args["content"])}


async def make_metric(ctx: ToolContext, args: dict) -> dict:
    block: dict[str, Any] = {"type": "metric", "label": args["label"], "value": args["value"]}
    if args.get("unit"):
        block["unit"] = args["unit"]
    if args.get("trend"):
        block["trend"] = args["trend"]
    await ctx.emit("block", block)
    return {"emitted": "metric", "label": args["label"]}


async def make_table(ctx: ToolContext, args: dict) -> dict:
    block: dict[str, Any] = {"type": "table", "columns": args["columns"], "rows": args["rows"]}
    if args.get("title"):
        block["title"] = args["title"]
    await ctx.emit("block", block)
    return {"emitted": "table", "rows": len(args["rows"])}


async def make_timeline(ctx: ToolContext, args: dict) -> dict:
    block: dict[str, Any] = {"type": "timeline", "events": args["events"]}
    if args.get("title"):
        block["title"] = args["title"]
    await ctx.emit("block", block)
    return {"emitted": "timeline", "events": len(args["events"])}


async def make_chart(ctx: ToolContext, args: dict) -> dict:
    refs: list[str] = args["refs"]
    unknown = [r for r in refs if r not in ctx.data_cache]
    if unknown:
        return {"error": f"unknown refs: {unknown} (call a data tool that returns a ref first)"}

    primary_ref = refs[0]
    if len(refs) > 1:
        merged: list[dict] = []
        for r in refs:
            merged.extend(ctx.data_cache[r])
        primary_ref = f"merged://{abs(hash(tuple(refs))):x}"
        await ctx.put_traces(primary_ref, merged)

    block: dict[str, Any] = {
        "type": "chart",
        "renderer": "plotly",
        "spec": {"layout": args.get("layout") or {}},
        "dataRef": primary_ref,
    }
    if args.get("title"):
        block["title"] = args["title"]
    await ctx.emit("block", block)
    return {"emitted": "chart", "title": args.get("title")}


EMIT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "make_markdown",
            "description": (
                "Emit a markdown block to the user's response. Use for prose: the summary, "
                "explanations, and any narrative sections. Supports GitHub-flavored markdown."
            ),
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_metric",
            "description": "Emit a headline metric card (label + value, optional unit and trend). Use for the key numbers in your answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"description": "Numeric or string value."},
                    "unit": {"type": "string"},
                    "trend": {"type": "string", "enum": ["up", "down", "flat"]},
                },
                "required": ["label", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_table",
            "description": "Emit a table. Use for tabular data, comparisons, and grids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "string"}},
                    "rows": {"type": "array", "items": {"type": "array"}},
                    "title": {"type": "string"},
                },
                "required": ["columns", "rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_chart",
            "description": "Emit a chart from one or more data refs (returned by a data tool, e.g. sample_series). Pass `refs`, an optional `title`, and Plotly `layout` overrides.",
            "parameters": {
                "type": "object",
                "properties": {
                    "refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "title": {"type": "string"},
                    "layout": {"type": "object", "description": "Plotly layout overrides, e.g. {yaxis:{title:'Value'}}."},
                },
                "required": ["refs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_timeline",
            "description": "Emit a vertical event timeline. Each event has ts (ISO 8601 or date), label, optional severity (info|warn|error). Use for dated events or milestones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ts": {"type": "string"},
                                "label": {"type": "string"},
                                "severity": {"type": "string", "enum": ["info", "warn", "error"]},
                            },
                            "required": ["ts", "label"],
                        },
                    },
                    "title": {"type": "string"},
                },
                "required": ["events"],
            },
        },
    },
]

EMIT_HANDLERS = {
    "make_markdown": make_markdown,
    "make_metric": make_metric,
    "make_table": make_table,
    "make_timeline": make_timeline,
    "make_chart": make_chart,
}
