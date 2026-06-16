import { Box } from '@mui/material'
import { ConversationList } from './Sidebar/ConversationList'
import { Transcript } from './Transcript'
import { PromptInput } from './PromptInput'

export function Shell() {
  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: 'background.default' }}>
      <ConversationList />
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
        }}
      >
        <Transcript />
        <Box sx={{ px: 4, bgcolor: 'background.default' }}>
          <Box sx={{ maxWidth: 920, mx: 'auto' }}>
            <PromptInput />
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
