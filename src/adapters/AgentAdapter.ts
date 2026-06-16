import type { EngineAdapter } from '../types/adapter'
import type { PromptRequest } from '../types/prompt'
import type { AgentEvent } from '../types/agentEvents'
import { parseSSE } from '../lib/sseParser'
import { apiBase } from '../lib/apiBase'

const API_BASE: string = apiBase()

export class AgentAdapter implements EngineAdapter {
  constructor(private readonly base: string = API_BASE) {}

  private postJson(req: PromptRequest, signal?: AbortSignal): Promise<Response> {
    const body = {
      prompt: req.prompt,
      context: req.context
        ? {
            conversation_id: req.context.conversationId,
          }
        : undefined,
    }
    return fetch(`${this.base}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      credentials: 'include',
      signal,
    })
  }

  private postUpload(req: PromptRequest, file: File, signal?: AbortSignal): Promise<Response> {
    // Multipart: the file is extracted to text server-side, so the (large)
    // document text never round-trips back through the browser. Let the browser
    // set the multipart Content-Type/boundary — don't set it manually.
    const form = new FormData()
    form.append('prompt', req.prompt)
    form.append('file', file)
    if (req.context?.conversationId) form.append('conversation_id', req.context.conversationId)
    return fetch(`${this.base}/chat/upload`, {
      method: 'POST',
      headers: { Accept: 'text/event-stream' },
      body: form,
      credentials: 'include',
      signal,
    })
  }

  async *stream(req: PromptRequest, signal?: AbortSignal): AsyncIterable<AgentEvent> {
    const res = req.file
      ? await this.postUpload(req, req.file, signal)
      : await this.postJson(req, signal)

    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => '')
      yield { type: 'error', error: `agent http ${res.status}: ${text || res.statusText}` }
      yield { type: 'done' }
      return
    }

    const reader = res.body.getReader()
    try {
      for await (const frame of parseSSE(reader)) {
        const ev = frameToEvent(frame.event, frame.data)
        if (ev) yield ev
      }
    } finally {
      reader.releaseLock()
    }
  }
}

function frameToEvent(event: string, raw: string): AgentEvent | null {
  let data: any
  try {
    data = raw ? JSON.parse(raw) : {}
  } catch {
    return { type: 'error', error: `malformed sse data for event '${event}'` }
  }
  switch (event) {
    case 'start':
      return { type: 'start', engine: data.engine }
    case 'thinking':
      return { type: 'thinking', text: data.text ?? '' }
    case 'narrative':
      return { type: 'narrative', text: data.text ?? '' }
    case 'tool_call':
      return { type: 'tool_call', id: data.id, name: data.name, args: data.args }
    case 'tool_result':
      return {
        type: 'tool_result',
        id: data.id,
        name: data.name,
        summary: data.summary ?? '',
        is_error: !!data.is_error,
      }
    case 'data':
      return { type: 'data', ref: data.ref, traces: data.traces ?? [] }
    case 'block':
      return { type: 'block', block: data }
    case 'metadata':
      return { type: 'metadata', metadata: data.metadata ?? data }
    case 'done':
      return { type: 'done' }
    case 'error':
      return { type: 'error', error: data.error ?? 'unknown error' }
    default:
      return null
  }
}
