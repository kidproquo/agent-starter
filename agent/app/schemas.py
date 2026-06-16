from typing import Any, Literal

from pydantic import BaseModel, Field


class PromptContext(BaseModel):
    # Text extracted server-side from an uploaded/attached document, passed to
    # the agent as grounding context.
    attachment_text: str | None = None
    # Ties multiple turns together into one conversation (multi-turn memory).
    conversation_id: str | None = None


class PromptRequest(BaseModel):
    prompt: str
    context: PromptContext | None = None


# RenderBlock variants (mirror frontend src/types/blocks.ts)


class MarkdownBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    content: str


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    renderer: Literal["plotly"] = "plotly"
    spec: dict[str, Any] = Field(default_factory=dict)
    dataRef: str | None = None
    title: str | None = None


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    rows: list[list[Any]]
    title: str | None = None


class MetricBlock(BaseModel):
    type: Literal["metric"] = "metric"
    label: str
    value: float | int | str
    unit: str | None = None
    trend: Literal["up", "down", "flat"] | None = None


class TimelineEvent(BaseModel):
    ts: str
    label: str
    severity: Literal["info", "warn", "error"] | None = None


class TimelineBlock(BaseModel):
    type: Literal["timeline"] = "timeline"
    events: list[TimelineEvent]
    title: str | None = None


RenderBlock = MarkdownBlock | ChartBlock | TableBlock | MetricBlock | TimelineBlock
