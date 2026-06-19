import { useEffect, useRef, useState } from 'react'
import {
  Box,
  Button,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined'
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined'
import TuneIcon from '@mui/icons-material/Tune'
import LogoutIcon from '@mui/icons-material/Logout'
import { useConversationStore } from '../../state/conversationStore'
import { useColorMode } from '../../state/uiStore'
import { useAuth, type UsageReport } from '../../auth/AuthContext'
import { costForUsageByModel, formatUsd, totalTokens } from '../../lib/pricing'
import { LlmSettingsModal } from '../LlmSettingsModal'

function usageLine(u: UsageReport | null): { tok: number; cost: number } {
  if (!u) return { tok: 0, cost: 0 }
  return { tok: totalTokens(u), cost: costForUsageByModel(u.models) }
}

function usageTooltip(u: UsageReport): string {
  const parts = [
    `in ${(u.input_tokens ?? 0).toLocaleString()}`,
    `out ${(u.output_tokens ?? 0).toLocaleString()}`,
    `cache hit ${(u.cache_read_input_tokens ?? 0).toLocaleString()}`,
    `cache write ${(u.cache_creation_input_tokens ?? 0).toLocaleString()}`,
    `${u.turns} turn${u.turns === 1 ? '' : 's'}`,
  ]
  return parts.join(' · ')
}

export function ConversationList({ onNavigate }: { onNavigate?: () => void } = {}) {
  const conversations = useConversationStore((s) => s.conversations)
  const activeId = useConversationStore((s) => s.activeId)
  const setActive = useConversationStore((s) => s.setActive)
  const create = useConversationStore((s) => s.createConversation)
  const remove = useConversationStore((s) => s.deleteConversation)
  const streaming = useConversationStore((s) => s.streaming)
  const { mode, toggle } = useColorMode()
  const { state, logout, refreshUsage } = useAuth()
  const [settingsOpen, setSettingsOpen] = useState(false)

  const user = state.status === 'authenticated' ? state.user : null
  const usage = state.status === 'authenticated' ? state.usage : null

  // Refresh the server-side usage tally each time a turn finishes streaming.
  const wasStreaming = useRef(false)
  useEffect(() => {
    const now = !!streaming
    if (wasStreaming.current && !now) void refreshUsage()
    wasStreaming.current = now
  }, [streaming, refreshUsage])

  const mine = usageLine(usage)
  const all = usage?.all_users ? usageLine(usage.all_users) : null

  return (
    <Stack
      sx={{
        width: { xs: '100%', md: 260 },
        flexShrink: 0,
        borderRight: { xs: 0, md: 1 },
        borderColor: 'divider',
        height: '100%',
        bgcolor: 'background.paper',
      }}
    >
      <Box sx={{ px: 2, py: 1.6, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: 0.2 }}>
          Agent Starter
        </Typography>
        <Typography variant="caption" color="text.secondary">
          litellm tool-use agent
        </Typography>
      </Box>

      <Box sx={{ p: 1.2 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={() => {
            create()
            onNavigate?.()
          }}
          sx={{ justifyContent: 'flex-start', borderColor: 'divider' }}
        >
          New conversation
        </Button>
      </Box>

      <List dense sx={{ flex: 1, overflowY: 'auto', px: 0.5 }}>
        {conversations.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1, display: 'block' }}>
            No conversations yet. Ask something below to begin.
          </Typography>
        )}
        {conversations.map((inv) => (
          <ListItemButton
            key={inv.id}
            selected={inv.id === activeId}
            onClick={() => {
              setActive(inv.id)
              onNavigate?.()
            }}
            sx={{
              borderRadius: 1,
              mx: 0.5,
              mb: 0.3,
              '&.Mui-selected': { bgcolor: 'action.selected' },
            }}
          >
            <ListItemText
              primary={inv.title}
              secondary={`${inv.turns.length} turn${inv.turns.length === 1 ? '' : 's'}`}
              primaryTypographyProps={{
                fontSize: '0.85rem',
                noWrap: true,
                fontWeight: inv.id === activeId ? 600 : 400,
              }}
              secondaryTypographyProps={{ fontSize: '0.72rem' }}
            />
            <Tooltip title="Delete">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  remove(inv.id)
                }}
              >
                <DeleteOutlineIcon fontSize="inherit" />
              </IconButton>
            </Tooltip>
          </ListItemButton>
        ))}
      </List>

      {/* Footer: per-user usage readout + identity + actions. */}
      <Box sx={{ p: 1.5, borderTop: 1, borderColor: 'divider' }}>
        {usage && (
          <Tooltip
            title={
              <Box sx={{ fontSize: '0.72rem' }}>
                <div>you · last all-time</div>
                <div>{usageTooltip(usage)}</div>
                {usage.all_users && (
                  <Box sx={{ mt: 0.5 }}>
                    <div>all users</div>
                    <div>{usageTooltip(usage.all_users)}</div>
                  </Box>
                )}
              </Box>
            }
          >
            <Box sx={{ mb: 1 }}>
              <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'lowercase' }}>
                usage: {mine.tok.toLocaleString()} tok · {formatUsd(mine.cost)}
              </Typography>
              {all && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', textTransform: 'lowercase', opacity: 0.8 }}
                >
                  all users: {all.tok.toLocaleString()} tok · {formatUsd(all.cost)}
                </Typography>
              )}
            </Box>
          </Tooltip>
        )}

        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }} noWrap>
              {user?.username ?? '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'lowercase' }}>
              {user?.role ?? ''}
            </Typography>
          </Box>
          <Stack direction="row" spacing={0.2}>
            {user?.role === 'admin' && (
              <Tooltip title="LLM model + API key">
                <IconButton size="small" onClick={() => setSettingsOpen(true)} aria-label="llm settings">
                  <TuneIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
              <IconButton size="small" onClick={toggle} aria-label="toggle color mode">
                {mode === 'dark' ? (
                  <LightModeOutlinedIcon fontSize="small" />
                ) : (
                  <DarkModeOutlinedIcon fontSize="small" />
                )}
              </IconButton>
            </Tooltip>
            <Tooltip title="Sign out">
              <IconButton size="small" onClick={() => void logout()} aria-label="sign out">
                <LogoutIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
        </Stack>
      </Box>

      {user?.role === 'admin' && (
        <LlmSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      )}
    </Stack>
  )
}
