import type { Scatter2DGraph } from '@/utils/api-client/interfaces/embedding';

/** Keep only points whose entity_id is in the allowed set. */
export function filterScatter2DGraph(
  graph: Scatter2DGraph,
  allowedEntityIds: ReadonlySet<string>
): Scatter2DGraph {
  if (allowedEntityIds.size === 0) {
    return { ...graph, points: [], clusters: [] };
  }

  const points = graph.points.filter(p => allowedEntityIds.has(p.entity_id));
  const clusterIndices = new Set(points.map(p => p.cluster_index));
  const clusters = graph.clusters.filter(c =>
    clusterIndices.has(c.cluster_index)
  );

  return { ...graph, points, clusters };
}
