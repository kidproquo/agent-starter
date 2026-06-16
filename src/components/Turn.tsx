import { Avatar, Box, Checkbox, Paper, Stack, Typography } from '@mui/material'
import PersonOutlineIcon from '@mui/icons-material/PersonOutline'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import type { Turn as TurnT, StreamingTurn } from '../state/conversationStore'
import { costForUsage, formatUsd } from '../lib/pricing'
import { BlockRenderer } from './blocks/BlockRenderer'
import { Scratchpad } from './Scratchpad'

type TurnLike = TurnT | (StreamingTurn & { id: string; createdAt: string })

export function Turn({
  turn,
  streaming = false,
  selectable = false,
  selected = false,
  onToggleSelect,
}: {
  turn: TurnLike
  streaming?: boolean
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: () => void
}) {
  return (
    <Stack
      spacing={2.5}
      onClick={selectable ? onToggleSelect : undefined}
      sx={{
        mb: 4,
        ...(selectable && {
          cursor: 'pointer',
          borderRadius: 2,
          p: 1.5,
          mx: -1.5,
          border: 1,
          borderColor: selected ? 'primary.main' : 'divider',
          bgcolor: selected ? 'action.selected' : 'transparent',
          transition: 'border-color 120ms ease, background-color 120ms ease',
          '&:hover': { borderColor: 'primary.main' },
        }),
      }}
    >
      {selectable && (
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: -1 }}>
          <Checkbox checked={selected} size="small" sx={{ p: 0.5 }} />
          <Typography variant="caption" color="text.secondary">
            {selected ? 'Included in report' : 'Click to include'}
          </Typography>
        </Stack>
      )}
      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        <Avatar sx={{ width: 28, height: 28, bgcolor: 'transparent', border: 1, borderColor: 'divider' }}>
          <PersonOutlineIcon fontSize="small" />
        </Avatar>
        <Paper
          variant="outlined"
          sx={{ flex: 1, px: 2, py: 1.4, borderColor: 'divider', bgcolor: 'background.paper' }}
        >
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            {turn.prompt}
          </Typography>
        </Paper>
      </Stack>

      <Stack direction="row" spacing={1.5} alignItems="flex-start">
        <Avatar
          sx={{
            width: 28,
            height: 28,
            bgcolor: 'transparent',
            border: 1,
            borderColor: 'primary.main',
            color: 'primary.main',
          }}
        >
          <TrendingUpIcon fontSize="small" />
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {turn.metadata && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 1, textTransform: 'lowercase' }}
            >
              {turn.metadata.engine ?? 'agent'}
              {(() => {
                const u = turn.metadata.usage
                if (!u) return null
                const parts: string[] = []
                if (u.input_tokens) parts.push(`in ${u.input_tokens.toLocaleString()}`)
                if (u.output_tokens) parts.push(`out ${u.output_tokens.toLocaleString()}`)
                if (u.cache_read_input_tokens)
                  parts.push(`cache hit ${u.cache_read_input_tokens.toLocaleString()}`)
                if (u.cache_creation_input_tokens)
                  parts.push(`cache write ${u.cache_creation_input_tokens.toLocaleString()}`)
                const cost = costForUsage(u, turn.metadata.engine ?? undefined)
                return (
                  <>
                    {parts.length > 0 && ` · ${parts.join(' · ')} tok`}
                    {cost > 0 && ` · ${formatUsd(cost)}`}
                  </>
                )
              })()}
              {turn.metadata.stop_reason && ` · ${turn.metadata.stop_reason}`}
            </Typography>
          )}

          <Scratchpad trace={turn.trace} defaultOpen={streaming} isStreaming={streaming} />

          <BlockRenderer blocks={turn.blocks} />

          {streaming && turn.blocks.length === 0 && <StreamingPlaceholder />}

          {turn.error && (
            <Box
              sx={{
                mt: 2,
                p: 1.4,
                border: 1,
                borderColor: 'error.main',
                borderRadius: 1,
                bgcolor: 'rgba(255,107,107,0.08)',
              }}
            >
              <Typography variant="caption" color="error.main">
                {turn.error}
              </Typography>
            </Box>
          )}
        </Box>
      </Stack>
    </Stack>
  )
}

function StreamingPlaceholder() {
  return (
    <Stack direction="row" spacing={0.6} sx={{ mt: 1.5 }}>
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            bgcolor: 'primary.main',
            opacity: 0.5,
            animation: 'vsPulse 1.2s infinite ease-in-out',
            animationDelay: `${i * 0.18}s`,
            '@keyframes vsPulse': {
              '0%, 80%, 100%': { opacity: 0.25, transform: 'scale(0.85)' },
              '40%': { opacity: 1, transform: 'scale(1.2)' },
            },
          }}
        />
      ))}
    </Stack>
  )
}
