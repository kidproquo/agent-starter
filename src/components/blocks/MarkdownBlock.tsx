import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Box, Typography } from '@mui/material'
import type { MarkdownBlock as MarkdownBlockT } from '../../types/blocks'

export function MarkdownBlock({ block }: { block: MarkdownBlockT }) {
  return (
    <Box
      sx={{
        // Break long unbreakable strings (URLs, tokens) instead of letting them
        // force horizontal scroll on the whole layout — critical on mobile.
        overflowWrap: 'anywhere',
        '& p': { m: 0, mb: 1.2, lineHeight: 1.65, fontSize: '0.92rem' },
        '& p:last-child': { mb: 0 },
        '& h3': { fontSize: '0.95rem', fontWeight: 600, mt: 2, mb: 0.8 },
        '& h2': { fontSize: '1.05rem', fontWeight: 600, mt: 2.2, mb: 1 },
        '& ul, & ol': { pl: 3, my: 1, '& li': { mb: 0.4 } },
        '& code': {
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.84em',
          bgcolor: 'rgba(255,255,255,0.06)',
          px: 0.6,
          py: 0.2,
          borderRadius: 0.6,
        },
        // Fenced code blocks scroll horizontally on their own rather than
        // widening the turn; reset the inline-code chrome inside them.
        '& pre': {
          overflowX: 'auto',
          bgcolor: 'rgba(255,255,255,0.06)',
          p: 1.2,
          borderRadius: 1,
          my: 1,
          '& code': { bgcolor: 'transparent', p: 0 },
        },
        // Wide GFM tables get their own horizontal scroll region.
        '& table': {
          display: 'block',
          overflowX: 'auto',
          borderCollapse: 'collapse',
          my: 1,
          fontSize: '0.86rem',
          '& th, & td': { border: 1, borderColor: 'divider', px: 1, py: 0.5, textAlign: 'left' },
        },
        '& strong': { fontWeight: 600 },
        '& a': { color: 'primary.main' },
      }}
    >
      <Typography component="div" variant="body2" color="text.primary">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.content}</ReactMarkdown>
      </Typography>
    </Box>
  )
}
