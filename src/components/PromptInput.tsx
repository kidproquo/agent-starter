import {
  useState,
  useCallback,
  useRef,
  ChangeEvent,
  DragEvent,
  KeyboardEvent,
} from 'react'
import {
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  TextField,
  Tooltip,
  CircularProgress,
  Typography,
} from '@mui/material'
import SendIcon from '@mui/icons-material/Send'
import StopIcon from '@mui/icons-material/Stop'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined'
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined'
import { useConverse } from '../query/useConverse'
import { useActiveConversation, useConversationStore } from '../state/conversationStore'
import { costForUsage, formatUsd, sumUsage, totalTokens } from '../lib/pricing'

// Accepted document formats for the optional attachment: PDF, HTML, and text.
const ACCEPT = '.pdf,.htm,.html,.txt,.text,.md,.markdown,.csv,.json,.xml,application/pdf,text/*'
const MAX_BYTES = 25 * 1024 * 1024

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export function PromptInput() {
  const [value, setValue] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [attachError, setAttachError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const { submit, cancel, isStreaming, error } = useConverse()
  const conversation = useActiveConversation()
  const streaming = useConversationStore((s) => s.streaming)
  const selectMode = useConversationStore((s) => s.selectMode)
  const enterSelectMode = useConversationStore((s) => s.enterSelectMode)

  const turns = conversation?.turns ?? []
  const canExportReport = turns.length > 0 && !selectMode && !isStreaming

  // Session usage: sum every completed turn plus the live one (if it belongs
  // to the active conversation). Cost is computed per-turn against its own model
  // so mixed-model sessions price correctly.
  const liveTurn =
    streaming && (!conversation || streaming.conversationId === conversation.id)
      ? [{ metadata: streaming.metadata }]
      : []
  const aggregate = sumUsage([...turns, ...liveTurn])
  const totalTok = totalTokens(aggregate)
  const totalCost = [...turns, ...liveTurn].reduce((sum, t) => {
    const u = t.metadata?.usage
    if (!u) return sum
    return sum + costForUsage(u, t.metadata?.engine ?? undefined)
  }, 0)

  // Prompt history navigation (↑/↓). -1 means "live draft", 0 = newest historical.
  const history = turns.map((t) => t.prompt)
  const historyIdx = useRef(-1)
  const draft = useRef('')

  const setCaretToEnd = () => {
    const ta = inputRef.current as HTMLTextAreaElement | null
    if (!ta) return
    requestAnimationFrame(() => {
      const len = ta.value.length
      ta.selectionStart = ta.selectionEnd = len
    })
  }

  const acceptFile = useCallback((f: File) => {
    if (f.size > MAX_BYTES) {
      setAttachError(`"${f.name}" is too large (max ${MAX_BYTES / (1024 * 1024)} MB).`)
      return
    }
    setAttachError(null)
    setFile(f)
  }, [])

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) acceptFile(f)
    e.target.value = '' // allow re-picking the same filename
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    if (isStreaming) return
    const f = e.dataTransfer.files?.[0]
    if (f) acceptFile(f)
  }

  const onSubmit = useCallback(() => {
    if (isStreaming) return
    const typed = value.trim()
    if (!typed && !file) return
    // A file with no question still gets a sensible default instruction.
    const prompt = typed || 'Summarize the attached document.'
    submit({ prompt, file: file ?? undefined })
    setValue('')
    setFile(null)
    setAttachError(null)
    historyIdx.current = -1
    draft.current = ''
  }, [value, file, isStreaming, submit])

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const ta = inputRef.current as HTMLTextAreaElement | null
    const caret = ta?.selectionStart ?? value.length

    // ↑ on the first line recalls the previous prompt; re-pressing goes older.
    if (e.key === 'ArrowUp' && !e.shiftKey && !e.altKey && !e.metaKey && !e.ctrlKey) {
      const onFirstLine = value.slice(0, caret).indexOf('\n') === -1
      if (!onFirstLine || history.length === 0) return
      e.preventDefault()
      if (historyIdx.current === -1) draft.current = value
      const next = Math.min(historyIdx.current + 1, history.length - 1)
      historyIdx.current = next
      setValue(history[history.length - 1 - next])
      setCaretToEnd()
      return
    }

    // ↓ on the last line walks back toward the live draft.
    if (e.key === 'ArrowDown' && !e.shiftKey && !e.altKey && !e.metaKey && !e.ctrlKey) {
      const onLastLine = value.slice(caret).indexOf('\n') === -1
      if (!onLastLine || historyIdx.current === -1) return
      e.preventDefault()
      const next = historyIdx.current - 1
      historyIdx.current = next
      setValue(next === -1 ? draft.current : history[history.length - 1 - next])
      setCaretToEnd()
      return
    }

    // Enter submits; Shift/Alt+Enter and ⌘/Ctrl+Enter insert a newline.
    if (e.key !== 'Enter' || e.shiftKey || e.altKey) return
    e.preventDefault()
    if (e.metaKey || e.ctrlKey) {
      const start = ta?.selectionStart ?? value.length
      const end = ta?.selectionEnd ?? value.length
      const next = value.slice(0, start) + '\n' + value.slice(end)
      setValue(next)
      requestAnimationFrame(() => {
        if (!ta) return
        ta.selectionStart = ta.selectionEnd = start + 1
      })
      return
    }
    onSubmit()
  }

  const onChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setValue(e.target.value)
    // Once the user edits, drop history-nav state — the buffer is now their
    // own working draft, not a recalled entry.
    historyIdx.current = -1
  }

  const canSend = !!value.trim() || !!file

  return (
    <Box sx={{ position: 'sticky', bottom: 0, pt: 2, pb: 2.5, bgcolor: 'background.default' }}>
      {(totalTok > 0 || canExportReport) && (
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.6 }}>
          {totalTok > 0 && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ textTransform: 'lowercase' }}
              title={`input ${aggregate.input_tokens?.toLocaleString()} · output ${aggregate.output_tokens?.toLocaleString()} · cache hit ${aggregate.cache_read_input_tokens?.toLocaleString()} · cache write ${aggregate.cache_creation_input_tokens?.toLocaleString()}`}
            >
              session: {totalTok.toLocaleString()} tok · {formatUsd(totalCost)}
            </Typography>
          )}
          <Box sx={{ flex: 1 }} />
          {canExportReport && (
            <Button
              size="small"
              startIcon={<IosShareOutlinedIcon fontSize="small" />}
              onClick={enterSelectMode}
              sx={{ textTransform: 'none', minWidth: 0, py: 0 }}
            >
              Export report
            </Button>
          )}
        </Box>
      )}
      {file && (
        <Box sx={{ mb: 0.8 }}>
          <Chip
            size="small"
            icon={<DescriptionOutlinedIcon />}
            label={`${file.name} · ${formatBytes(file.size)}`}
            onDelete={() => setFile(null)}
            disabled={isStreaming}
            sx={{ maxWidth: '100%' }}
          />
        </Box>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={onPickFile}
      />
      <Paper
        variant="outlined"
        onDragOver={(e) => {
          e.preventDefault()
          if (!isStreaming) setDragOver(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          setDragOver(false)
        }}
        onDrop={onDrop}
        sx={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 1,
          p: 1.2,
          borderColor: dragOver ? 'primary.main' : 'divider',
          borderStyle: dragOver ? 'dashed' : 'solid',
          bgcolor: 'background.paper',
          transition: 'border-color 120ms ease',
        }}
      >
        <Tooltip title="Attach a document (PDF, HTML, or text)">
          <span>
            <IconButton
              onClick={() => fileInputRef.current?.click()}
              disabled={isStreaming}
              sx={{ alignSelf: 'flex-end' }}
            >
              <AttachFileIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <TextField
          multiline
          minRows={1}
          maxRows={6}
          fullWidth
          variant="standard"
          placeholder={
            dragOver
              ? 'Drop the file to attach it…'
              : 'Ask a question, or attach a document for context…'
          }
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          disabled={isStreaming}
          inputRef={inputRef}
          InputProps={{ disableUnderline: true, sx: { fontSize: '0.95rem', px: 1 } }}
        />
        {isStreaming ? (
          <Tooltip title="Stop">
            <IconButton color="error" onClick={cancel} sx={{ alignSelf: 'flex-end' }}>
              <StopIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title="Send (Enter) · Newline (⌘/Ctrl + Enter)">
            <span>
              <IconButton
                color="primary"
                onClick={onSubmit}
                disabled={!canSend}
                sx={{ alignSelf: 'flex-end' }}
              >
                <SendIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        )}
      </Paper>
      {isStreaming && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
          <CircularProgress size={12} />
          <Box sx={{ fontSize: '0.78rem' }}>Working…</Box>
        </Box>
      )}
      {attachError && <Box sx={{ mt: 1, color: 'error.main', fontSize: '0.8rem' }}>{attachError}</Box>}
      {error && <Box sx={{ mt: 1, color: 'error.main', fontSize: '0.8rem' }}>{error}</Box>}
    </Box>
  )
}
