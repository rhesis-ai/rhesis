export interface ScatterPoint2D {
  embedding_id: string;
  entity_id: string;
  entity_type: string;
  cluster_index: number;
  searchable_text: string;
  x: number;
  y: number;
}

export interface Cluster {
  cluster_index: number;
  label: string;
  size: number;
}

export interface Scatter2DGraph {
  computed_at: string;
  clusters: Cluster[];
  points: ScatterPoint2D[];
}

export interface EmbeddingGraphComputeResponse {
  status: 'pending';
  task_id: string;
}

export type EmbeddingGraphGetResponse =
  | { status: 'pending' }
  | { status: 'ready'; graph: Scatter2DGraph };
