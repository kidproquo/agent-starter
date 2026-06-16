import { useMemo } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-cartesian-dist-min'
import { Box, Skeleton, Typography, useTheme } from '@mui/material'
import type { ChartBlock as ChartBlockT } from '../../types/blocks'
import { useDataRef } from '../../query/useDataRef'

// react-plotly.js/factory + plotly.js-cartesian-dist-min: cartesian-only bundle (no mapbox/maplibre/webgl),
// matching drift. We only render line/bar charts, so the full plotly.js-dist-min is unnecessary weight.
const Plot = createPlotlyComponent(Plotly as unknown as Parameters<typeof createPlotlyComponent>[0])

export default function ChartBlockPlotly({ block }: { block: ChartBlockT }) {
  const theme = useTheme()
  const { data, isLoading, error } = useDataRef<unknown[]>(block.dataRef)

  const layout = useMemo(() => {
    const userLayout = (block.spec?.layout as Record<string, unknown>) ?? {}
    return {
      autosize: true,
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      colorway: ['#4ade80', '#d4b483', '#7c9cff', '#ff9f43'],
      font: {
        color: theme.palette.text.primary,
        family: theme.typography.fontFamily,
        size: 11,
      },
      margin: { l: 56, r: 16, t: 16, b: 44 },
      xaxis: {
        gridcolor: 'rgba(255,255,255,0.06)',
        zerolinecolor: 'rgba(255,255,255,0.1)',
        ...(userLayout.xaxis as object),
      },
      yaxis: {
        gridcolor: 'rgba(255,255,255,0.06)',
        zerolinecolor: 'rgba(255,255,255,0.1)',
        ...(userLayout.yaxis as object),
      },
      legend: { bgcolor: 'rgba(0,0,0,0)', orientation: 'h', y: -0.2 },
      ...userLayout,
    }
  }, [block.spec, theme])

  if (isLoading) {
    return <Skeleton variant="rounded" height={320} />
  }
  if (error) {
    const isAgentRef = (block.dataRef ?? '').includes('://')
    return (
      <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
        {isAgentRef
          ? 'Chart data is no longer in cache (the page was reloaded). Re-run the prompt to refetch.'
          : `Failed to load chart data: ${(error as Error).message}`}
      </Typography>
    )
  }
  if (!data) return null

  return (
    <Box sx={{ width: '100%', height: 340 }}>
      <Plot
        data={data as Plotly.Data[]}
        layout={layout as Partial<Plotly.Layout>}
        config={{ displaylogo: false, responsive: true, displayModeBar: 'hover' }}
        useResizeHandler
        style={{ width: '100%', height: '100%' }}
      />
    </Box>
  )
}
