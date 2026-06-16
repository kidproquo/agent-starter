import React, { useMemo } from 'react'
import ReactDOM from 'react-dom/client'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { makeTheme } from './theme'
import { useColorMode } from './state/uiStore'
import { AuthProvider } from './auth/AuthContext'
import { queryClient } from './query/client'
import { prefetchPricing } from './lib/pricing'

// Warm the model-pricing table so the usage cost shows real numbers on first
// paint instead of the static fallback.
void prefetchPricing()

// Rebuilds the MUI theme whenever the resolved color mode changes (user toggle
// or, until they override, the OS setting).
function ThemedApp() {
  const { mode } = useColorMode()
  const theme = useMemo(() => makeTheme(mode), [mode])
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <App />
      </AuthProvider>
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemedApp />
    </QueryClientProvider>
  </React.StrictMode>,
)
