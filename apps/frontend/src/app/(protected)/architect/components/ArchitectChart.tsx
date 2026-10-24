'use client';

import * as React from 'react';
import {
  Box,
  Button,
  Menu,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import { BarChart } from '@mui/x-charts/BarChart';
import { LineChart } from '@mui/x-charts/LineChart';
import { ScatterChart } from '@mui/x-charts/ScatterChart';
import { RadarChart } from '@mui/x-charts/RadarChart';
import { ChartsReferenceLine } from '@mui/x-charts/ChartsReferenceLine';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  ArchitectChartSpec,
  ChartMeasure,
  ChartPalette,
  buildSeries,
  categoryColors,
  dataColumns,
  formatDimension,
  formatMeasure,
  hasGoodDirection,
  heatPosition,
  humanize,
  legendEntries,
  seriesColors,
  seriesMark,
  seriesValues,
  valueBounds,
  xCategories,
} from '@/utils/architect/charts';
import {
  chartCsv,
  chartFileName,
  chartPng,
  chartSvg,
  downloadBlob,
  findChartSvg,
} from '@/utils/architect/chart-export';

const PLOT_HEIGHT = 280;
const VALUE_AXIS_WIDTH = 64;
// About five ticks keeps the value axis quiet: 0, 25, 50, 75, 100 rather than every 5%.
const VALUE_TICKS = 5;
const CROWDED_CATEGORIES = 4;
const ANGLED_LABEL_ALLOWANCE = 64;
// Room right of the plot for a vertical target line's label ("Target 90%").
const TARGET_LABEL_MARGIN = 88;
// Room right of the longest bar for its value label ("92.31%").
const VALUE_LABEL_MARGIN = 56;
// Horizontal bars grow with the number of categories so labels stay readable.
const HORIZONTAL_BAR_ROW_HEIGHT = 32;
const BAR_RADIUS = 4;
// The right margin leaves room for the last x label ("Week of Oct 12") to center on its tick.
const PLOT_MARGIN = { top: 16, right: 48, bottom: 32, left: 56 };
const QUIET_AXIS = { disableLine: true, disableTicks: true };
// Thinner bars than MUI's default leave the plot lighter and the gaps readable.
const CATEGORY_GAP_RATIO = 0.4;
// Past this many points the dots crowd the line, so only the line is drawn.
const MAX_MARKED_POINTS = 12;
const LEGEND_AT_START = {
  legend: { position: { vertical: 'top', horizontal: 'start' } },
} as const;

interface ArchitectChartProps {
  spec: ArchitectChartSpec;
}

function usePalette(): ChartPalette {
  return useTheme().chartPalettes.architect;
}

function ReferenceLine({
  spec,
  axis,
}: ArchitectChartProps & { axis: 'x' | 'y' }) {
  const theme = useTheme();
  if (spec.target === null || spec.target === undefined) return null;
  const props = {
    label: `Target ${formatMeasure(spec.target, spec.measures[0].kind)}`,
    // At the start of the line, where it can't collide with bar value labels.
    labelAlign: 'start' as const,
    lineStyle: {
      stroke: theme.palette.text.secondary,
      strokeDasharray: '4 4',
    },
    labelStyle: {
      fill: theme.palette.text.secondary,
      fontSize: theme.typography.caption.fontSize,
    },
  };
  return axis === 'x' ? (
    <ChartsReferenceLine x={spec.target} {...props} />
  ) : (
    <ChartsReferenceLine y={spec.target} {...props} />
  );
}

function CartesianChart({ spec }: ArchitectChartProps) {
  const palette = usePalette();
  const categories = xCategories(spec);
  const primary: ChartMeasure = spec.measures[0];
  const valueAxis = {
    ...valueBounds(primary.kind),
    ...QUIET_AXIS,
    tickNumber: VALUE_TICKS,
    // Room for the widest tick label ("$0.0450", "5.25 s").
    width: VALUE_AXIS_WIDTH,
    valueFormatter: (value: number | null) =>
      formatMeasure(value, primary.kind),
  };
  const built = buildSeries(spec);
  const colors = seriesColors(
    spec,
    built.map(s => s.label),
    palette,
    seriesMark(spec.chart_type)
  );
  const series = built.map((s, i) => ({
    data: s.data,
    label: s.label,
    color: colors[i],
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
        slotProps={LEGEND_AT_START}
        grid={{ horizontal: true }}
        // Ticks stay: without them the first x label crowds the "0%" below the plot.
        xAxis={[{ scaleType: 'point', data: categories, disableLine: true }]}
        yAxis={[area ? { min: 0, ...QUIET_AXIS } : valueAxis]}
        series={series.map(s => ({
          ...s,
          area,
          stack: area ? 'total' : undefined,
          connectNulls: true,
          // Straight segments: smoothing invents peaks between the real points.
          curve: 'linear' as const,
          showMark: categories.length <= MAX_MARKED_POINTS,
        }))}
      >
        <ReferenceLine spec={spec} axis="y" />
      </LineChart>
    );
  }

  const stacked = spec.chart_type === 'stacked_bar';
  const single = series.length === 1 && !stacked;
  // A focus on x values colors those bars; the rest of a lone series stays neutral.
  const barColors = single ? categoryColors(spec, categories, palette) : null;
  const bandAxis = {
    scaleType: 'band' as const,
    data: categories,
    ...QUIET_AXIS,
    categoryGapRatio: CATEGORY_GAP_RATIO,
    ...(barColors
      ? {
          colorMap: {
            type: 'ordinal' as const,
            values: categories,
            colors: barColors,
          },
        }
      : {}),
  };
  const countAxis = { min: 0, ...QUIET_AXIS, tickNumber: VALUE_TICKS };

  if (spec.chart_type === 'horizontal_bar') {
    // A ranked list reads by its values, so a lone series labels each bar.
    const labelled = single;
    const rightMargin = Math.max(
      spec.target != null ? TARGET_LABEL_MARGIN : 24,
      labelled ? VALUE_LABEL_MARGIN : 0
    );
    return (
      <BarChart
        height={Math.max(
          PLOT_HEIGHT,
          categories.length * HORIZONTAL_BAR_ROW_HEIGHT
        )}
        margin={{ ...PLOT_MARGIN, left: 16, right: rightMargin }}
        layout="horizontal"
        borderRadius={BAR_RADIUS}
        hideLegend={hideLegend}
        slotProps={LEGEND_AT_START}
        grid={{ vertical: true }}
        yAxis={[{ ...bandAxis, width: 160 }]}
        xAxis={[stacked ? countAxis : valueAxis]}
        series={series.map(s => ({
          ...s,
          stack: stacked ? 'total' : undefined,
          ...(labelled
            ? {
                barLabel: (item: { value: number | null }) =>
                  formatMeasure(item.value, primary.kind),
                barLabelPlacement: 'outside' as const,
              }
            : {}),
        }))}
      >
        <ReferenceLine spec={spec} axis="x" />
      </BarChart>
    );
  }

  // Past a few categories MUI drops overlapping labels; angle them so every bar is named.
  const crowded = categories.length > CROWDED_CATEGORIES;
  return (
    <BarChart
      height={PLOT_HEIGHT + (crowded ? ANGLED_LABEL_ALLOWANCE : 0)}
      margin={PLOT_MARGIN}
      borderRadius={BAR_RADIUS}
      hideLegend={hideLegend}
      slotProps={LEGEND_AT_START}
      grid={{ horizontal: true }}
      xAxis={[
        {
          ...bandAxis,
          ...(crowded
            ? {
                tickLabelInterval: () => true,
                tickLabelStyle: { angle: -30, textAnchor: 'end' },
                height: ANGLED_LABEL_ALLOWANCE,
              }
            : {}),
        },
      ]}
      yAxis={[stacked ? countAxis : valueAxis]}
      series={series.map(s => ({
        ...s,
        stack: stacked ? 'total' : undefined,
      }))}
    >
      <ReferenceLine spec={spec} axis="y" />
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
      grid={{ horizontal: true, vertical: true }}
      xAxis={[
        {
          ...valueBounds(xMeasure.kind),
          ...QUIET_AXIS,
          tickNumber: VALUE_TICKS,
          label: humanize(xMeasure.key),
          valueFormatter: (v: number | null) => formatMeasure(v, xMeasure.kind),
        },
      ]}
      yAxis={[
        {
          ...valueBounds(yMeasure.kind),
          ...QUIET_AXIS,
          tickNumber: VALUE_TICKS,
          label: humanize(yMeasure.key),
          valueFormatter: (v: number | null) => formatMeasure(v, yMeasure.kind),
        },
      ]}
      series={[
        {
          color: palette.series[0],
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
  const built = buildSeries(spec);
  const colors = seriesColors(
    spec,
    built.map(s => s.label),
    palette,
    'line'
  );
  return (
    <RadarChart
      height={PLOT_HEIGHT}
      hideLegend={!spec.series}
      slotProps={LEGEND_AT_START}
      radar={{
        metrics: xCategories(spec),
        ...(valueBounds(measure.kind).max !== undefined
          ? { max: valueBounds(measure.kind).max }
          : {}),
      }}
      series={built.map((s, i) => ({
        label: s.label,
        data: s.data.map(v => v ?? 0),
        color: colors[i],
        valueFormatter: (value: number | null) =>
          formatMeasure(value, measure.kind),
      }))}
    />
  );
}

function HeatTable({ spec }: ArchitectChartProps) {
  const theme = useTheme();
  const palette = usePalette();
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
    if (!hasGoodDirection(measure.kind)) {
      return alpha(palette.series[0], position * 0.6);
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

interface ExportMenuProps extends ArchitectChartProps {
  plotRef: React.RefObject<HTMLDivElement | null>;
}

/** CSV always; PNG and SVG while a plot is on screen (not for tables or the KPI). */
function ExportMenu({ spec, plotRef }: ExportMenuProps) {
  const theme = useTheme();
  const palette = usePalette();
  const notifications = useNotifications();
  const [anchor, setAnchor] = React.useState<HTMLElement | null>(null);
  const [plot, setPlot] = React.useState<SVGSVGElement | null>(null);

  const open = (event: React.MouseEvent<HTMLElement>) => {
    setPlot(findChartSvg(plotRef.current));
    setAnchor(event.currentTarget);
  };
  const close = () => setAnchor(null);

  const image = (svg: SVGSVGElement) =>
    chartSvg(svg, {
      title: spec.title,
      legend: legendEntries(spec, palette),
      background: theme.palette.background.paper,
      textColor: theme.palette.text.primary,
      fontFamily: String(theme.typography.fontFamily),
    });

  const exportAs = async (format: 'png' | 'svg' | 'csv') => {
    close();
    try {
      if (format === 'csv') {
        const blob = new Blob([chartCsv(spec)], {
          type: 'text/csv;charset=utf-8',
        });
        downloadBlob(blob, chartFileName(spec, 'csv'));
        return;
      }
      if (!plot) return;
      const rendered = image(plot);
      const blob =
        format === 'svg'
          ? new Blob([rendered.markup], { type: 'image/svg+xml;charset=utf-8' })
          : await chartPng(rendered);
      downloadBlob(blob, chartFileName(spec, format));
    } catch (error) {
      console.error('Architect chart export failed:', error);
      notifications.show('The chart could not be exported', {
        severity: 'error',
      });
    }
  };

  return (
    <>
      <Button
        size="small"
        startIcon={<FileDownloadOutlinedIcon fontSize="small" />}
        aria-haspopup="menu"
        aria-expanded={anchor ? 'true' : undefined}
        onClick={open}
      >
        Export
      </Button>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        {plot && (
          <MenuItem onClick={() => exportAs('png')}>Image (PNG)</MenuItem>
        )}
        {plot && (
          <MenuItem onClick={() => exportAs('svg')}>Vector (SVG)</MenuItem>
        )}
        <MenuItem onClick={() => exportAs('csv')}>Data (CSV)</MenuItem>
      </Menu>
    </>
  );
}

/** One chart from the Architect's show_chart tool, with a toggle to its exact numbers. */
export default function ArchitectChart({ spec }: ArchitectChartProps) {
  const [showData, setShowData] = React.useState(false);
  const plotRef = React.useRef<HTMLDivElement>(null);
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
        <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
          <ExportMenu spec={spec} plotRef={plotRef} />
          {canToggle && (
            <Button size="small" onClick={() => setShowData(v => !v)}>
              {showData ? 'Show chart' : 'Show data'}
            </Button>
          )}
        </Box>
      </Box>
      <Box ref={plotRef}>
        {showData ? <DataTable spec={spec} /> : <ChartBody spec={spec} />}
      </Box>
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
