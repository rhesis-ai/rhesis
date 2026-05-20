import type { Theme } from '@mui/material/styles';
import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import {
  graphToEmbeddingViewData,
  type EmbeddingViewData,
  type EmbeddingViewLabel,
} from './graphToEmbeddingViewData';

export type EmbeddingColorBy = 'cluster' | 'behavior' | 'category' | 'topic';

export const EMBEDDING_COLOR_BY_OPTIONS: {
  value: EmbeddingColorBy;
  label: string;
}[] = [
  { value: 'cluster', label: 'Cluster' },
  { value: 'behavior', label: 'Behavior' },
  { value: 'category', label: 'Category' },
  { value: 'topic', label: 'Topic' },
];

export const UNASSIGNED_COLOR_LABEL = 'Unassigned';

export interface EmbeddingChartColors {
  unassigned: string;
  other: string;
  palette: readonly string[];
}

/** Resolve embedding scatter colors from the active MUI theme. */
export function getEmbeddingChartColors(theme: Theme): EmbeddingChartColors {
  return {
    unassigned: theme.palette.grey[500],
    other: theme.palette.grey[600],
    palette: theme.chartPalettes.categorical,
  };
}

export interface EmbeddingColorLegendEntry {
  label: string;
  color: string;
  count: number;
}

export interface EmbeddingChartColorConfig {
  category: Uint8Array;
  categoryColors: string[];
  labels: EmbeddingViewLabel[] | null;
  legend: EmbeddingColorLegendEntry[];
  viewMode: 'points' | 'density';
}

/** Uint8 max; index 0 reserved for unassigned / overflow bucket. */
const MAX_NAMED_CATEGORIES = 254;

function paletteColor(index: number, palette: readonly string[]): string {
  return palette[index % palette.length];
}

function getDimensionValue(
  test: TestDetail | undefined,
  colorBy: EmbeddingColorBy
): string | null {
  if (!test) return null;
  switch (colorBy) {
    case 'behavior':
      return test.behavior?.name ?? null;
    case 'category':
      return test.category?.name ?? null;
    case 'topic':
      return test.topic?.name ?? null;
    default:
      return null;
  }
}

function buildClusterLegend(
  graph: Scatter2DGraph,
  colors: EmbeddingChartColors
): EmbeddingColorLegendEntry[] {
  const countByCluster = new Map<number, number>();
  for (const point of graph.points) {
    countByCluster.set(
      point.cluster_index,
      (countByCluster.get(point.cluster_index) ?? 0) + 1
    );
  }

  const uniqueIndices = [
    ...new Set(graph.points.map(p => p.cluster_index)),
  ].sort((a, b) => a - b);

  return uniqueIndices
    .map((clusterIndex, i) => {
      const cluster = graph.clusters.find(
        c => c.cluster_index === clusterIndex
      );
      const isNoise = clusterIndex === -1;
      return {
        label:
          cluster?.label ??
          (isNoise ? 'Unclustered' : `Cluster ${clusterIndex}`),
        color: isNoise ? colors.unassigned : paletteColor(i, colors.palette),
        count: countByCluster.get(clusterIndex) ?? 0,
      };
    })
    .filter(entry => entry.count > 0);
}

function buildClusterColorConfig(
  graph: Scatter2DGraph,
  baseViewData: EmbeddingViewData,
  colors: EmbeddingChartColors
): EmbeddingChartColorConfig {
  const maxCategoryIndex = baseViewData.category.reduce(
    (max, c) => Math.max(max, c),
    0
  );
  const categoryColors: string[] = [];
  for (let i = 0; i <= maxCategoryIndex; i++) {
    const clusterIndex = [
      ...new Set(graph.points.map(p => p.cluster_index)),
    ].sort((a, b) => a - b)[i];
    categoryColors.push(
      clusterIndex === -1 ? colors.unassigned : paletteColor(i, colors.palette)
    );
  }

  return {
    category: baseViewData.category,
    categoryColors,
    labels: baseViewData.labels,
    legend: buildClusterLegend(graph, colors),
    viewMode: 'density',
  };
}

function buildMetadataColorConfig(
  graph: Scatter2DGraph,
  tests: TestDetail[],
  colorBy: EmbeddingColorBy,
  colors: EmbeddingChartColors
): EmbeddingChartColorConfig {
  const testsById = new Map<string, TestDetail>(tests.map(t => [t.id, t]));
  const valueCounts = new Map<string, number>();

  for (const point of graph.points) {
    const raw = getDimensionValue(testsById.get(point.entity_id), colorBy);
    const key = raw?.trim() || UNASSIGNED_COLOR_LABEL;
    valueCounts.set(key, (valueCounts.get(key) ?? 0) + 1);
  }

  const namedValues = [...valueCounts.keys()]
    .filter(k => k !== UNASSIGNED_COLOR_LABEL)
    .sort((a, b) => a.localeCompare(b));

  let valuesForIndex = namedValues;
  let otherCount = 0;
  if (namedValues.length > MAX_NAMED_CATEGORIES) {
    valuesForIndex = namedValues.slice(0, MAX_NAMED_CATEGORIES - 1);
    otherCount = namedValues
      .slice(MAX_NAMED_CATEGORIES - 1)
      .reduce((sum, name) => sum + (valueCounts.get(name) ?? 0), 0);
  }

  const indexByValue = new Map<string, number>();
  indexByValue.set(UNASSIGNED_COLOR_LABEL, 0);
  valuesForIndex.forEach((name, i) => {
    indexByValue.set(name, i + 1);
  });
  const otherIndex = valuesForIndex.length + 1;
  if (otherCount > 0) {
    indexByValue.set('Other', otherIndex);
  }

  const category = new Uint8Array(graph.points.length);
  for (let i = 0; i < graph.points.length; i++) {
    const point = graph.points[i];
    const raw = getDimensionValue(testsById.get(point.entity_id), colorBy);
    const key = raw?.trim() || UNASSIGNED_COLOR_LABEL;
    if (key === UNASSIGNED_COLOR_LABEL) {
      category[i] = 0;
    } else if (indexByValue.has(key)) {
      category[i] = indexByValue.get(key)!;
    } else {
      category[i] = otherIndex;
    }
  }

  const maxIndex = category.reduce((max, c) => Math.max(max, c), 0);
  const categoryColors: string[] = [colors.unassigned];
  for (let i = 1; i <= maxIndex; i++) {
    categoryColors.push(paletteColor(i - 1, colors.palette));
  }
  if (otherCount > 0) {
    categoryColors[otherIndex] = colors.other;
  }

  const legend: EmbeddingColorLegendEntry[] = [];
  const unassignedCount = valueCounts.get(UNASSIGNED_COLOR_LABEL) ?? 0;
  if (unassignedCount > 0) {
    legend.push({
      label: UNASSIGNED_COLOR_LABEL,
      color: colors.unassigned,
      count: unassignedCount,
    });
  }
  valuesForIndex.forEach((name, i) => {
    legend.push({
      label: name,
      color: paletteColor(i, colors.palette),
      count: valueCounts.get(name) ?? 0,
    });
  });
  if (otherCount > 0) {
    legend.push({
      label: 'Other',
      color: colors.other,
      count: otherCount,
    });
  }

  return {
    category,
    categoryColors,
    labels: null,
    legend,
    viewMode: 'points',
  };
}

export function buildEmbeddingChartColorConfig(
  graph: Scatter2DGraph,
  tests: TestDetail[],
  colorBy: EmbeddingColorBy,
  colors: EmbeddingChartColors
): EmbeddingChartColorConfig | null {
  const baseViewData = graphToEmbeddingViewData(graph);
  if (!baseViewData) return null;

  if (colorBy === 'cluster') {
    return buildClusterColorConfig(graph, baseViewData, colors);
  }
  return buildMetadataColorConfig(graph, tests, colorBy, colors);
}

/** Base coordinates and entity ids — shared across color-by modes. */
export function getEmbeddingBaseViewData(
  graph: Scatter2DGraph
): EmbeddingViewData | null {
  return graphToEmbeddingViewData(graph);
}
