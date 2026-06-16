import type { EngineAdapter } from '../types/adapter'
import type { PromptRequest } from '../types/prompt'
import type { AgentEvent } from '../types/agentEvents'

/**
 * Offline stand-in for the litellm backend. Emits a canned conversation so the
 * UI is explorable without an API key or a running backend. Mirrors the event
 * protocol the real AgentAdapter receives over SSE. Selected by building with
 * VITE_ENGINE=mock (see src/adapters/index.ts).
 */
export class MockAdapter implements EngineAdapter {
  async *stream(_req: PromptRequest, signal?: AbortSignal): AsyncIterable<AgentEvent> {
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

    yield { type: 'start', engine: 'mock' }
    await sleep(150)

    yield { type: 'thinking', text: 'Deciding which tools to call…' }
    await sleep(200)

    const ref = 'series://sine/mock'
    for (const tc of MOCK_TOOLCALLS(ref)) {
      if (signal?.aborted) return
      yield { type: 'tool_call', id: tc.id, name: tc.name, args: tc.args }
      await sleep(180)
      if (tc.data) yield { type: 'data', ref: tc.data.ref, traces: tc.data.traces }
      yield { type: 'tool_result', id: tc.id, name: tc.name, summary: tc.summary, is_error: false }
    }

    yield {
      type: 'block',
      block: {
        type: 'markdown',
        content: '**Here is a sample answer.** This is mock data rendered from the same block protocol the real agent uses.',
      },
    }
    await sleep(120)

    for (const m of [
      { label: 'Result', value: '65536', trend: 'flat' as const },
      { label: 'Points', value: '50', trend: 'flat' as const },
      { label: 'Peak', value: '1.0', trend: 'up' as const },
    ]) {
      yield { type: 'block', block: { type: 'metric', ...m } }
      await sleep(60)
    }

    yield {
      type: 'block',
      block: {
        type: 'chart',
        renderer: 'plotly',
        dataRef: ref,
        title: 'Sample series',
        spec: { layout: { yaxis: { title: 'Value' } } },
      },
    }
    await sleep(120)

    yield {
      type: 'block',
      block: {
        type: 'table',
        title: 'Options',
        columns: ['Option', 'Pro', 'Con'],
        rows: [
          ['A', 'Simple', 'Limited'],
          ['B', 'Flexible', 'More setup'],
          ['C', 'Fast', 'Less safe'],
        ],
      },
    }
    await sleep(120)

    yield {
      type: 'block',
      block: {
        type: 'markdown',
        content:
          '### Notes\n' +
          'Swap `MockAdapter` for the real `AgentAdapter` by building without `VITE_ENGINE=mock`. ' +
          'Replace the example backend tools to make this your own.',
      },
    }

    yield {
      type: 'metadata',
      metadata: { engine: 'mock', stop_reason: 'stop', usage: { input_tokens: 0, output_tokens: 0 } },
    }
    yield { type: 'done' }
  }
}

function MOCK_TOOLCALLS(ref: string) {
  const traces = mockSineTrace()
  return [
    {
      id: 't1',
      name: 'compute',
      args: { operation: 'power', a: 2, b: 16 },
      summary: 'power → 65536',
    },
    {
      id: 't2',
      name: 'sample_series',
      args: { points: 50, kind: 'sine' },
      summary: `50 pts · ref ${ref}`,
      data: { ref, traces },
    },
  ]
}

function mockSineTrace() {
  const x: number[] = []
  const y: number[] = []
  for (let i = 0; i < 50; i++) {
    x.push(i)
    y.push(Math.round(Math.sin(i / 4) * 10000) / 10000)
  }
  return [{ x, y, type: 'scatter', mode: 'lines', name: 'sine' }]
}
