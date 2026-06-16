import type { EngineAdapter } from '../types/adapter'
import { MockAdapter } from './MockAdapter'
import { AgentAdapter } from './AgentAdapter'

let cached: EngineAdapter | null = null

export function getAdapter(): EngineAdapter {
  if (cached) return cached
  const engine = (import.meta.env.VITE_ENGINE ?? 'agent').toString().toLowerCase()
  cached = engine === 'mock' ? new MockAdapter() : new AgentAdapter()
  return cached
}

export function resetAdapter(): void {
  cached = null
}
