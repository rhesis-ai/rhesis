/**
 * Chart specs the Architect's show_chart tool attaches to a reply, and the pure
 * helpers that turn their insights rows into series for `@mui/x-charts`.
 * The rows come from the insights query itself, never from the model.
 */

export type ArchitectChartType =
  | 'line'
  | 'area'
  | 'bar'
  | 'horizontal_bar'
  | 'stacked_bar'
  | 'scatter'
  | 'heat_table'
  | 'radar'
  | 'kpi';

/** From the insights registry: a rate is 0-100, a score is 0-1, a count is a whole number. */
export type MeasureKind = 'count' | 'rate' | 'score';

export interface ChartMeasure {
  key: string;
  kind: MeasureKind;
}

export type ChartRow = Record<string, string | number | boolean | null>;

export interface ArchitectChartSpec {
  title: string;
  chart_type: ArchitectChartType;
  entity?: string | null;
  x?: string | null;
  series?: string | null;
  measures: ChartMeasure[];
  time_grain?: string | null;
  target?: number | null;
  rows: ChartRow[];
  truncated?: boolean;
}

export interface ChartSeries {
  label: string;
  measure: ChartMeasure;
  data: Array<number | null>;
}

const PERIOD = 'period';
const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/** "pass_rate" -> "Pass rate", "test_run" -> "Test run". */
export function humanize(key: string): string {
  const words = key.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function formatMeasure(
  value: number | null | undefined,
  kind: MeasureKind
): string {
  if (value === null || value === undefined) return '';
  if (kind === 'rate') return `${Number(value.toFixed(1))}%`;
  if (kind === 'score') return value.toFixed(2);
  return value.toLocaleString();
}

/** Period values are ISO bucket start dates in UTC; label them by their grain. */
export function formatPeriod(value: string, grain?: string | null): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month) return value;
  const monthName = MONTHS[month - 1];
  switch (grain) {
    case 'year':
      return `${year}`;
    case 'quarter':
      return `Q${Math.floor((month - 1) / 3) + 1} ${year}`;
    case 'week':
      return `Week of ${monthName} ${day}`;
    case 'day':
      return `${monthName} ${day}, ${year}`;
    default:
      return `${monthName} ${year}`;
  }
}

export function formatDimension(
  spec: ArchitectChartSpec,
  dimension: string,
  value: ChartRow[string]
): string {
  if (value === null || value === undefined || value === '') return '(none)';
  if (dimension === PERIOD && typeof value === 'string') {
    return formatPeriod(value, spec.time_grain);
  }
  return String(value);
}

/** Distinct values of a dimension, in the order the query returned them. */
function distinctValues(spec: ArchitectChartSpec, dimension: string): string[] {
  const seen = new Set<string>();
  for (const row of spec.rows) {
    seen.add(formatDimension(spec, dimension, row[dimension]));
  }
  return [...seen];
}

export function xCategories(spec: ArchitectChartSpec): string[] {
  return spec.x ? distinctValues(spec, spec.x) : [];
}

export function seriesValues(spec: ArchitectChartSpec): string[] {
  return spec.series ? distinctValues(spec, spec.series) : [];
}

function numeric(value: ChartRow[string]): number | null {
  return typeof value === 'number' ? value : null;
}

/**
 * One series per series-dimension value (plotting the first measure), or one
 * per measure when there is no series dimension. Data aligns with `xCategories`.
 */
export function buildSeries(spec: ArchitectChartSpec): ChartSeries[] {
  const x = spec.x;
  if (!x) return [];
  const categories = xCategories(spec);
  const index = new Map(categories.map((c, i) => [c, i]));

  if (spec.series) {
    const seriesDim = spec.series;
    const measure = spec.measures[0];
    const bySeries = new Map<string, Array<number | null>>();
    for (const row of spec.rows) {
      const label = formatDimension(spec, seriesDim, row[seriesDim]);
      const data =
        bySeries.get(label) ?? new Array(categories.length).fill(null);
      const position = index.get(formatDimension(spec, x, row[x]));
      if (position !== undefined) data[position] = numeric(row[measure.key]);
      bySeries.set(label, data);
    }
    return [...bySeries.entries()].map(([label, data]) => ({
      label,
      measure,
      data,
    }));
  }

  return spec.measures.map(measure => {
    const data: Array<number | null> = new Array(categories.length).fill(null);
    for (const row of spec.rows) {
      const position = index.get(formatDimension(spec, x, row[x]));
      if (position !== undefined) data[position] = numeric(row[measure.key]);
    }
    return { label: humanize(measure.key), measure, data };
  });
}

/** Value axis bounds: rates span 0-100 and scores 0-1, so bars compare honestly. */
export function valueBounds(kind: MeasureKind): {
  min?: number;
  max?: number;
} {
  if (kind === 'rate') return { min: 0, max: 100 };
  if (kind === 'score') return { min: 0, max: 1 };
  return { min: 0 };
}

/**
 * Where a value sits between bad (0) and good (1), for heat-table shading.
 * Counts have no good direction, so they shade by size relative to the largest.
 */
export function heatPosition(
  value: number,
  kind: MeasureKind,
  maxCount: number
): number {
  if (kind === 'rate') return Math.min(Math.max(value / 100, 0), 1);
  if (kind === 'score') return Math.min(Math.max(value, 0), 1);
  return maxCount > 0 ? value / maxCount : 0;
}

/** Table columns for the "show data" view: x, series, then the measures. */
export function dataColumns(spec: ArchitectChartSpec): string[] {
  return [
    ...[spec.x, spec.series].filter((d): d is string => Boolean(d)),
    ...spec.measures.map(m => m.key),
  ];
}
