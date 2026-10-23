'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import { ScatterChart } from '@mui/x-charts/ScatterChart';
import { RadarChart } from '@mui/x-charts/RadarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  ArchitectChartSpec,
  ChartMeasure,
  buildSeries,
  dataColumns,
  formatDimension,
  formatMeasure,
  heatPosition,
  humanize,
  seriesValues,
  valueBounds,
  xCategories,
} from '@/utils/architect/charts';

const PLOT_HEIGHT = 280;
// Horizontal bars grow with the number of categories so labels stay readable.
const HORIZONTAL_BAR_ROW_HEIGHT = 32;
const PLOT_MARGIN = { top: 16, right: 16, bottom: 32, left: 56 };

interface ArchitectChartProps {
  spec: ArchitectChartSpec;
}

function usePalette(): string[] {
  const theme = useTheme();
  return theme.chartPalettes.categorical;
}

function referenceLine(spec: ArchitectChartSpec, axis: 'x' | 'y') {
  if (spec.target === null || spec.target === undefined) return null;
  const label = `Target ${formatMeasure(spec.target, spec.measures[0].kind)}`;
  return axis === 'x' ? (
    <ChartsReferenceLine x={spec.target} label={label} />
  ) : (
    <ChartsReferenceLine y={spec.target} label={label} />
  );
}

function CartesianChart({ spec }: ArchitectChartProps) {
  const palette = usePalette();
  const categories = xCategories(spec);
  const primary: ChartMeasure = spec.measures[0];
  const valueAxis = {
    ...valueBounds(primary.kind),
    valueFormatter: (value: number | null) =>
      formatMeasure(value, primary.kind),
  };
  const series = buildSeries(spec).map((s, i) => ({
    data: s.data,
    label: s.label,
    color: palette[i % palette.length],
    valueFormatter: (value: number | null) =>
      formatMeasure(value, s.measure.kind),
  }));
  const hideLegend = series.length < 2;

  if (spec.chart_type === 'line' || spec.chart_type === 'area') {
    const area = spec.chart_type === 'area';
    return (
      <LineChart
        height={PLOT_HEIGHT}
        margin={PLOT_MARGIN}
        hideLegend={hideLegend}
        xAxis={[{ scaleType: 'point', data: categories }]}
        yAxis={[area ? { min: 0 } : valueAxis]}
        series={series.map(s => ({
          ...s,
          area,
          stack: area ? 'total' : undefined,
          connectNulls: true,
        }))}
      >
        {referenceLine(spec, 'y')}
      </LineChart>
    );
  }

  const stacked = spec.chart_type === 'stacked_bar';
  const stackedSeries = series.map(s => ({
    ...s,
    stack: stacked ? 'total' : undefined,
  }));
  const countAxis = { min: 0 };

  if (spec.chart_type === 'horizontal_bar') {
    return (
      <BarChart
        height={Math.max(
          PLOT_HEIGHT,
          categories.length * HORIZONTAL_BAR_ROW_HEIGHT
        )}
        margin={{ ...PLOT_MARGIN, left: 16 }}
        layout="horizontal"
        hideLegend={hideLegend}
        yAxis={[{ scaleType: 'band', data: categories, width: 160 }]}
        xAxis={[stacked ? countAxis : valueAxis]}
        series={stackedSeries}
      >
        {referenceLine(spec, 'x')}
      </BarChart>
    );
  }

  return (
    <BarChart
      height={PLOT_HEIGHT}
      margin={PLOT_MARGIN}
      hideLegend={hideLegend}
      xAxis={[{ scaleType: 'band', data: categories }]}
      yAxis={[stacked ? countAxis : valueAxis]}
      series={stackedSeries}
    >
      {referenceLine(spec, 'y')}
    </BarChart>
  );
}

function Scatter({ spec }: ArchitectChartProps) {
  const palette = usePalette();
  const [xMeasure, yMeasure] = spec.measures;
  const x = spec.x ?? '';
  return (
    <ScatterChart
      height={PLOT_HEIGHT}
      margin={PLOT_MARGIN}
      hideLegend
      xAxis={[
        {
          ...valueBounds(xMeasure.kind),
          label: humanize(xMeasure.key),
          valueFormatter: (v: number | null) => formatMeasure(v, xMeasure.kind),
        },
      ]}
      yAxis={[
        {
          ...valueBounds(yMeasure.kind),
          label: humanize(yMeasure.key),
          valueFormatter: (v: number | null) => formatMeasure(v, yMeasure.kind),
        },
      ]}
      series={[
        {
          color: palette[0],
          data: spec.rows.flatMap((row, i) => {
            const xv = row[xMeasure.key];
            const yv = row[yMeasure.key];
            if (typeof xv !== 'number' || typeof yv !== 'number') return [];
            return [{ x: xv, y: yv, id: String(row[`${x}_id`] ?? i) }];
          }),
          valueFormatter: (_value, { dataIndex }) =>
            formatDimension(spec, x, spec.rows[dataIndex]?.[x]),
        },
      ]}
    />
  );
}

function Radar({ spec }: ArchitectChartProps) {
  const palette = usePalette();
  const measure = spec.measures[0];
  return (
    <RadarChart
      height={PLOT_HEIGHT}
      hideLegend={!spec.series}
      radar={{
        metrics: xCategories(spec),
        ...(valueBounds(measure.kind).max !== undefined
          ? { max: valueBounds(measure.kind).max }
          : {}),
      }}
      series={buildSeries(spec).map((s, i) => ({
        label: s.label,
        data: s.data.map(v => v ?? 0),
        color: palette[i % palette.length],
        valueFormatter: (value: number | null) =>
          formatMeasure(value, measure.kind),
      }))}
    />
  );
}

function HeatTable({ spec }: ArchitectChartProps) {
  const theme = useTheme();
  const measure = spec.measures[0];
  const rows = xCategories(spec);
  const columns = seriesValues(spec);
  const x = spec.x ?? '';
  const seriesDim = spec.series ?? '';
  const cells = new Map<string, number | null>();
  let maxCount = 0;
  for (const row of spec.rows) {
    const value = row[measure.key];
    const numeric = typeof value === 'number' ? value : null;
    if (numeric !== null) maxCount = Math.max(maxCount, numeric);
    cells.set(
      `${formatDimension(spec, x, row[x])}\u0000${formatDimension(spec, seriesDim, row[seriesDim])}`,
      numeric
    );
  }

  const shade = (value: number) => {
    const position = heatPosition(value, measure.kind, maxCount);
    if (measure.kind === 'count') {
      return alpha(theme.palette.primary.main, position * 0.6);
    }
    // Good values lean green, poor values lean red, the middle stays neutral.
    return position >= 0.5
      ? alpha(theme.palette.success.main, (position - 0.5) * 1.2)
      : alpha(theme.palette.error.main, (0.5 - position) * 1.2);
  };

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{humanize(x)}</TableCell>
            {columns.map(column => (
              <TableCell key={column} align="center">
                {column}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map(rowLabel => (
            <TableRow key={rowLabel}>
              <TableCell component="th" scope="row">
                {rowLabel}
              </TableCell>
              {columns.map(column => {
                const value = cells.get(`${rowLabel}\u0000${column}`);
                return (
                  <TableCell
                    key={column}
                    align="center"
                    sx={{
                      bgcolor:
                        value === null || value === undefined
                          ? undefined
                          : shade(value),
                    }}
                  >
                    {value === null || value === undefined
                      ? '–'
                      : formatMeasure(value, measure.kind)}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function Kpi({ spec }: ArchitectChartProps) {
  const measure = spec.measures[0];
  const value = spec.rows[0]?.[measure.key];
  return (
    <Box sx={{ py: 2 }}>
      <Typography variant="h3" component="p">
        {typeof value === 'number' ? formatMeasure(value, measure.kind) : '–'}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {humanize(measure.key)}
        {spec.target !== null && spec.target !== undefined
          ? ` · target ${formatMeasure(spec.target, measure.kind)}`
          : ''}
      </Typography>
    </Box>
  );
}

function DataTable({ spec }: ArchitectChartProps) {
  const columns = dataColumns(spec);
  const kinds = new Map(spec.measures.map(m => [m.key, m.kind]));
  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map(column => (
              <TableCell
                key={column}
                align={kinds.has(column) ? 'right' : 'left'}
              >
                {humanize(column)}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {spec.rows.map((row, i) => (
            // Rows are a fixed query result that never reorders.
            // eslint-disable-next-line react/no-array-index-key
            <TableRow key={i}>
              {columns.map(column => {
                const kind = kinds.get(column);
                const value = row[column];
                return (
                  <TableCell key={column} align={kind ? 'right' : 'left'}>
                    {kind
                      ? formatMeasure(
                          typeof value === 'number' ? value : null,
                          kind
                        )
                      : formatDimension(spec, column, value)}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}

function ChartBody({ spec }: ArchitectChartProps) {
  switch (spec.chart_type) {
    case 'scatter':
      return <Scatter spec={spec} />;
    case 'radar':
      return <Radar spec={spec} />;
    case 'heat_table':
      return <HeatTable spec={spec} />;
    case 'kpi':
      return <Kpi spec={spec} />;
    default:
      return <CartesianChart spec={spec} />;
  }
}

/** One chart from the Architect's show_chart tool, with a toggle to its exact numbers. */
export default function ArchitectChart({ spec }: ArchitectChartProps) {
  const [showData, setShowData] = React.useState(false);
  const canToggle = spec.chart_type !== 'kpi';

  return (
    <Box
      sx={{
        border: theme => `1px solid ${theme.palette.divider}`,
        borderRadius: BORDER_RADIUS.sm,
        p: 1.5,
        mt: 1.5,
        bgcolor: 'background.paper',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
        }}
      >
        <Typography variant="subtitle2">{spec.title}</Typography>
        {canToggle && (
          <Button size="small" onClick={() => setShowData(v => !v)}>
            {showData ? 'Show chart' : 'Show data'}
          </Button>
        )}
      </Box>
      {showData ? <DataTable spec={spec} /> : <ChartBody spec={spec} />}
      {spec.truncated && (
        <Typography variant="caption" color="text.secondary">
          Showing the first {spec.rows.length} rows.
        </Typography>
      )}
    </Box>
  );
}

/** Keeps one malformed chart from taking the whole message down with it. */
export class ArchitectChartBoundary extends React.Component<
  { title: string; children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error('Architect chart failed to render:', error);
  }

  render() {
    if (this.state.failed) {
      return (
        <Typography variant="caption" color="text.secondary" component="p">
          The chart “{this.props.title}” could not be shown.
        </Typography>
      );
    }
    return this.props.children;
  }
}
