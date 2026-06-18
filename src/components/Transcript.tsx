import { useEffect, useRef } from 'react'
import { Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import CheckBoxOutlinedIcon from '@mui/icons-material/CheckBoxOutlined'
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined'
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined'
import { deriveTitle, useActiveConversation, useConversationStore } from '../state/conversationStore'
import { Turn } from './Turn'
import { useConverse } from '../query/useConverse'
import { downloadReport, printReport } from '../lib/exportReport'

const SUGGESTIONS = [
  'Compute 2^16 and chart the powers of two from 0 to 16.',
  'Give me a sample sine series over 50 points and plot it.',
  'Summarize what tools you have available.',
  'Make a small table comparing three options with pros and cons.',
]

export function Transcript() {
  const conversation = useActiveConversation()
  const streaming = useConversationStore((s) => s.streaming)
  const selectMode = useConversationStore((s) => s.selectMode)
  const selectedTurnIds = useConversationStore((s) => s.selectedTurnIds)
  const toggleTurnSelected = useConversationStore((s) => s.toggleTurnSelected)
  const selectAll = useConversationStore((s) => s.selectAllTurnsInActive)
  const exitSelectMode = useConversationStore((s) => s.exitSelectMode)
  const { submit, isStreaming } = useConverse()
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [conversation?.turns.length, streaming?.trace.length, streaming?.blocks.length])

  const turns = conversation?.turns ?? []
  const showStreaming = streaming && (!conversation || streaming.conversationId === conversation.id)
  const selectedTurns = turns.filter((t) => selectedTurnIds.has(t.id))

  const handleExport = (mode: 'html' | 'pdf') => {
    if (!conversation || selectedTurns.length === 0) return
    // Title the report from the first SELECTED turn, not conversation.title —
    // the latter is derived from the first prompt, which leaks into the export
    // even when that turn isn't selected.
    const title = deriveTitle(selectedTurns[0].prompt)
    const inputs = { title, turns: selectedTurns, exportedAt: new Date() }
    if (mode === 'pdf') printReport(inputs)
    else downloadReport(inputs)
    exitSelectMode()
  }

  return (
    <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: 4, py: 4 }}>
      {selectMode && (
        <Paper
          variant="outlined"
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 2,
            mb: 3,
            px: 2,
            py: 1.2,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <CheckBoxOutlinedIcon
            fontSize="small"
            color={selectedTurns.length > 0 ? 'primary' : 'disabled'}
          />
          <Typography variant="body2" sx={{ flex: 1 }}>
            {selectedTurns.length === 0
              ? 'Select turns to include in the report.'
              : `${selectedTurns.length} turn${selectedTurns.length === 1 ? '' : 's'} selected`}
          </Typography>
          <Button size="small" onClick={selectAll} sx={{ textTransform: 'none' }}>
            Select all
          </Button>
          <Button size="small" onClick={exitSelectMode} sx={{ textTransform: 'none' }}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<DownloadOutlinedIcon />}
            disabled={selectedTurns.length === 0}
            onClick={() => handleExport('html')}
            sx={{ textTransform: 'none' }}
          >
            HTML
          </Button>
          <Button
            size="small"
            variant="contained"
            startIcon={<PictureAsPdfOutlinedIcon />}
            disabled={selectedTurns.length === 0}
            onClick={() => handleExport('pdf')}
            sx={{ textTransform: 'none' }}
          >
            PDF
          </Button>
        </Paper>
      )}
      {turns.length === 0 && !showStreaming && (
        <EmptyState onPick={(text) => submit({ prompt: text })} disabled={isStreaming} />
      )}
      {turns.map((t) => (
        <Turn
          key={t.id}
          turn={t}
          selectable={selectMode}
          selected={selectedTurnIds.has(t.id)}
          onToggleSelect={() => toggleTurnSelected(t.id)}
        />
      ))}
      {showStreaming && !selectMode && (
        <Turn
          streaming
          turn={{
            id: streaming.turnId,
            prompt: streaming.prompt,
            trace: streaming.trace,
            blocks: streaming.blocks,
            metadata: streaming.metadata,
            error: streaming.error,
            createdAt: streaming.startedAt,
          }}
        />
      )}
      <div ref={bottomRef} />
    </Box>
  )
}

function EmptyState({ onPick, disabled }: { onPick: (text: string) => void; disabled: boolean }) {
  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', mt: 6 }}>
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
        What can I help you with?
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        This is a streaming tool-use agent. It reasons in a scratchpad and builds its
        answer from render blocks — markdown, metric cards, tables, charts, and timelines.
        Ask a question or attach a document to begin. Swap in your own tools under
        <code> agent/app/tools/</code> to make it yours.
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ textTransform: 'uppercase', letterSpacing: 0.4, mb: 1.2, display: 'block' }}
      >
        Try
      </Typography>
      <Stack spacing={1}>
        {SUGGESTIONS.map((text) => (
          <Chip
            key={text}
            label={text}
            variant="outlined"
            disabled={disabled}
            onClick={() => onPick(text)}
            sx={{
              justifyContent: 'flex-start',
              py: 2.4,
              borderRadius: 2,
              borderColor: 'divider',
              '& .MuiChip-label': { px: 1.4, fontSize: '0.85rem', whiteSpace: 'normal' },
              cursor: 'pointer',
              '&:hover': { bgcolor: 'action.hover' },
            }}
          />
        ))}
      </Stack>
    </Box>
  )
}
