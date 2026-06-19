import { Box, CircularProgress } from '@mui/material'
import { useAuth } from './auth/AuthContext'
import { LoginPage } from './components/LoginPage'
import { Shell } from './components/Shell'

export default function App() {
  const { state } = useAuth()

  if (state.status === 'loading') {
    return (
      <Box sx={{ height: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress size={24} />
      </Box>
    )
  }
  if (state.status === 'unauthenticated') {
    return <LoginPage />
  }
  return <Shell />
}
