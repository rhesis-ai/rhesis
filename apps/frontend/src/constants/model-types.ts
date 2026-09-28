/**
 * Model type constants matching the backend Model.model_type values
 */
export const MODEL_TYPES = {
  LANGUAGE: 'language',
  EMBEDDING: 'embedding',
  // Answers typed questions only (e.g. Jev); can judge categorical metrics, can't generate text.
  DECISION: 'decision',
} as const;

export type ModelType = (typeof MODEL_TYPES)[keyof typeof MODEL_TYPES];
