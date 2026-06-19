import { useState } from 'react'
import { Box, Drawer, IconButton, Typography, useMediaQuery, useTheme } from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import { ConversationList } from './Sidebar/ConversationList'
import { Transcript } from './Transcript'
import { PromptInput } from './PromptInput'

export function Shell() {
  const theme = useTheme()
  // Below `md`, the sidebar collapses into a slide-over drawer so the
  // transcript gets the full (narrow) viewport width.
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <Box sx={{ display: 'flex', height: '100dvh', bgcolor: 'background.default' }}>
      {isMobile ? (
        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{ '& .MuiDrawer-paper': { width: 280, boxSizing: 'border-box' } }}
        >
          <ConversationList onNavigate={() => setDrawerOpen(false)} />
        </Drawer>
      ) : (
        <ConversationList />
      )}
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100dvh',
        }}
      >
        {isMobile && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1,
              py: 0.5,
              borderBottom: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            <IconButton edge="start" onClick={() => setDrawerOpen(true)} aria-label="open menu">
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: 0.2 }}>
              Agent Starter
            </Typography>
          </Box>
        )}
        <Transcript />
        <Box sx={{ px: { xs: 1.5, sm: 4 }, bgcolor: 'background.default' }}>
          <Box sx={{ maxWidth: 920, mx: 'auto' }}>
            <PromptInput />
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
