import { lazy, Suspense } from 'react'
import { Box, Paper, Skeleton, Typography } from '@mui/material'
import type { ChartBlock as ChartBlockT } from '../../types/blocks'

const ChartBlockPlotly = lazy(() => import('./ChartBlock.plotly'))

export function ChartBlock({ block }: { block: ChartBlockT }) {
  return (
    <Paper variant="outlined" sx={{ borderColor: 'divider', p: 2 }}>
      {block.title && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ textTransform: 'uppercase', letterSpacing: 0.4, mb: 1.2, display: 'block' }}
        >
          {block.title}
        </Typography>
      )}
      <Suspense fallback={<Box sx={{ height: 340 }}><Skeleton variant="rounded" height="100%" /></Box>}>
        <ChartBlockPlotly block={block} />
      </Suspense>
    </Paper>
  )
}
