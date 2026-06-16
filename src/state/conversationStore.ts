import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { nanoid } from 'nanoid'
import type { RenderBlock } from '../types/blocks'
import type { TraceEntry } from '../types/agentEvents'

export type TurnMetadata = {
  engine?: string
  stop_reason?: string
  usage?: {
    input_tokens?: number
    output_tokens?: number
    cache_read_input_tokens?: number
    cache_creation_input_tokens?: number
  }
}

export type Turn = {
  id: string
  prompt: string
  trace: TraceEntry[]
  blocks: RenderBlock[]
  metadata?: TurnMetadata
  createdAt: string
  error?: string
}

export type Conversation = {
  id: string
  title: string
  turns: Turn[]
  createdAt: string
}

export type StreamingTurn = {
  conversationId: string
  turnId: string
  prompt: string
  trace: TraceEntry[]
  blocks: RenderBlock[]
  metadata?: TurnMetadata
  startedAt: string
  error?: string
}

type Store = {
  conversations: Conversation[]
  activeId: string | null
  streaming: StreamingTurn | null

  // Transient "select turns to export" mode. Not persisted (see partialize).
  selectMode: boolean
  selectedTurnIds: Set<string>

  createConversation(): string
  setActive(id: string): void
  deleteConversation(id: string): void
  renameConversation(id: string, title: string): void

  enterSelectMode(): void
  exitSelectMode(): void
  toggleTurnSelected(id: string): void
  selectAllTurnsInActive(): void

  beginStream(prompt: string): { conversationId: string; turnId: string }
  appendThinking(text: string): void
  appendNarrative(text: string): void
  upsertToolCall(id: string, name: string, args: unknown): void
  finishToolCall(id: string, summary: string, isError: boolean): void
  addBlock(block: RenderBlock): void
  setStreamMetadata(metadata: TurnMetadata): void
  setStreamError(error: string): void
  finalizeStream(): void
  abortStream(): void
}

function deriveTitle(prompt: string): string {
  const trimmed = prompt.trim().replace(/\s+/g, ' ')
  return trimmed.length <= 60 ? trimmed : trimmed.slice(0, 57) + '…'
}

function pushTraceText(
  trace: TraceEntry[],
  kind: 'thinking' | 'narrative',
  text: string,
): TraceEntry[] {
  const last = trace[trace.length - 1]
  if (last && last.kind === kind) {
    return [...trace.slice(0, -1), { kind, text: last.text + text }]
  }
  return [...trace, { kind, text }]
}

export const useConversationStore = create<Store>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeId: null,
      streaming: null,
      selectMode: false,
      selectedTurnIds: new Set<string>(),

      createConversation() {
        const id = nanoid(10)
        set((s) => ({
          conversations: [
            {
              id,
              title: 'New conversation',
              turns: [],
              createdAt: new Date().toISOString(),
            },
            ...s.conversations,
          ],
          activeId: id,
        }))
        return id
      },

      setActive(id) {
        // Leaving the current conversation abandons any in-progress selection.
        set({ activeId: id, selectMode: false, selectedTurnIds: new Set() })
      },

      deleteConversation(id) {
        set((s) => {
          const remaining = s.conversations.filter((i) => i.id !== id)
          return {
            conversations: remaining,
            activeId: s.activeId === id ? remaining[0]?.id ?? null : s.activeId,
          }
        })
      },

      renameConversation(id, title) {
        set((s) => ({
          conversations: s.conversations.map((i) => (i.id === id ? { ...i, title } : i)),
        }))
      },

      enterSelectMode() {
        set({ selectMode: true, selectedTurnIds: new Set() })
      },

      exitSelectMode() {
        set({ selectMode: false, selectedTurnIds: new Set() })
      },

      toggleTurnSelected(id) {
        set((s) => {
          const next = new Set(s.selectedTurnIds)
          if (next.has(id)) next.delete(id)
          else next.add(id)
          return { selectedTurnIds: next }
        })
      },

      selectAllTurnsInActive() {
        set((s) => {
          const active = s.conversations.find((i) => i.id === s.activeId)
          if (!active) return s
          return { selectedTurnIds: new Set(active.turns.map((t) => t.id)) }
        })
      },

      beginStream(prompt) {
        let activeId = get().activeId
        if (!activeId || !get().conversations.some((i) => i.id === activeId)) {
          activeId = get().createConversation()
        }
        const turnId = nanoid(10)
        set({
          streaming: {
            conversationId: activeId!,
            turnId,
            prompt,
            trace: [],
            blocks: [],
            startedAt: new Date().toISOString(),
          },
        })
        return { conversationId: activeId!, turnId }
      },

      appendThinking(text) {
        set((s) =>
          s.streaming
            ? { streaming: { ...s.streaming, trace: pushTraceText(s.streaming.trace, 'thinking', text) } }
            : s,
        )
      },

      appendNarrative(text) {
        set((s) =>
          s.streaming
            ? { streaming: { ...s.streaming, trace: pushTraceText(s.streaming.trace, 'narrative', text) } }
            : s,
        )
      },

      upsertToolCall(id, name, args) {
        set((s) => {
          if (!s.streaming) return s
          const exists = s.streaming.trace.some((t) => t.kind === 'tool_call' && t.id === id)
          if (exists) return s
          return {
            streaming: {
              ...s.streaming,
              trace: [...s.streaming.trace, { kind: 'tool_call', id, name, args, status: 'pending' }],
            },
          }
        })
      },

      finishToolCall(id, summary, isError) {
        set((s) => {
          if (!s.streaming) return s
          return {
            streaming: {
              ...s.streaming,
              trace: s.streaming.trace.map((t) =>
                t.kind === 'tool_call' && t.id === id
                  ? { ...t, status: isError ? 'error' : 'done', summary }
                  : t,
              ),
            },
          }
        })
      },

      addBlock(block) {
        set((s) =>
          s.streaming ? { streaming: { ...s.streaming, blocks: [...s.streaming.blocks, block] } } : s,
        )
      },

      setStreamMetadata(metadata) {
        set((s) => (s.streaming ? { streaming: { ...s.streaming, metadata } } : s))
      },

      setStreamError(error) {
        set((s) => (s.streaming ? { streaming: { ...s.streaming, error } } : s))
      },

      finalizeStream() {
        const { streaming, conversations } = get()
        if (!streaming) return
        const turn: Turn = {
          id: streaming.turnId,
          prompt: streaming.prompt,
          trace: streaming.trace,
          blocks: streaming.blocks,
          metadata: streaming.metadata,
          error: streaming.error,
          createdAt: streaming.startedAt,
        }
        set({
          conversations: conversations.map((inv) =>
            inv.id === streaming.conversationId
              ? {
                  ...inv,
                  title: inv.turns.length === 0 ? deriveTitle(streaming.prompt) : inv.title,
                  turns: [...inv.turns, turn],
                }
              : inv,
          ),
          streaming: null,
        })
      },

      abortStream() {
        set({ streaming: null })
      },
    }),
    {
      name: 'app.conversations.v1',
      partialize: (s) => ({
        conversations: s.conversations,
        activeId: s.activeId,
      }),
    },
  ),
)

export function useActiveConversation(): Conversation | null {
  return useConversationStore((s) => {
    const id = s.activeId
    if (!id) return null
    return s.conversations.find((i) => i.id === id) ?? null
  })
}
