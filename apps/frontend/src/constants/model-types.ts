/**
 * Model type constants matching the backend Model.model_type values
 */
export const MODEL_TYPES = {
  LANGUAGE: 'language',
  EMBEDDING: 'embedding',
  // Answers typed questions only (e.g. Jev); can judge categorical metrics, can't generate text.
  DECISION: 'decision',
} as const;

/** OData filter for the type lookups that list model providers. */
export const PROVIDER_TYPE_LOOKUP_FILTER = "type_name eq 'ProviderType'";

export type ModelType = (typeof MODEL_TYPES)[keyof typeof MODEL_TYPES];
