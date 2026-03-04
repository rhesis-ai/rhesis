/**
 * Score type constants matching the backend ScoreType enum
 */
export const SCORE_TYPES = {
  NUMERIC: 'numeric',
  CATEGORICAL: 'categorical',
} as const;

/**
 * Type for score type values
 */
export type ScoreTypeValue = (typeof SCORE_TYPES)[keyof typeof SCORE_TYPES];
