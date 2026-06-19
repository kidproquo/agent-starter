import { createTheme } from '@mui/material/styles'

export type ColorMode = 'light' | 'dark'

// Shared, mode-independent tokens.
const typography = {
  fontFamily:
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontSize: 13,
  h6: { fontWeight: 600, fontSize: '0.95rem' },
  body2: { lineHeight: 1.55 },
} as const

// Muted green accent palette. Dark slate by default; a clean off-white paper
// variant for light mode (deeper green for contrast). Tweak to taste.
export function makeTheme(mode: ColorMode) {
  const isDark = mode === 'dark'
  return createTheme({
    palette: {
      mode,
      primary: { main: isDark ? '#4ade80' : '#15803d' },
      secondary: { main: isDark ? '#d4b483' : '#a16207' },
      background: isDark
        ? { default: '#0d1117', paper: '#161b22' }
        : { default: '#f6f7f9', paper: '#ffffff' },
      divider: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.1)',
    },
    typography,
    shape: { borderRadius: 8 },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          // Comfort bump for the whole type scale. Body text, captions, and
          // headings are all sized in rem, so raising the root font size scales
          // everything up uniformly without disturbing the visual hierarchy.
          // Adjust this one value to make the UI text larger or smaller.
          html: { fontSize: '18px' },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: { root: { textTransform: 'none', fontWeight: 500 } },
      },
    },
  })
}
