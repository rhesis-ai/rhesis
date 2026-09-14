import {
  ANNOTATION_TARGET_TYPES,
  type AnnotationSummaryEntry,
} from '@/utils/api-client/interfaces/annotation';

type Summary = Record<string, AnnotationSummaryEntry> | undefined | null;

/**
 * The annotation on each metric, keyed by metric name.
 *
 * `annotation_summary` is already one entry per target, so there is no
 * newest-wins comparison to make here.
 */
export function annotationsByMetric(
  summary: Summary
): Map<string, AnnotationSummaryEntry> {
  const map = new Map<string, AnnotationSummaryEntry>();
  for (const entry of Object.values(summary ?? {})) {
    if (
      entry.target_type === ANNOTATION_TARGET_TYPES.METRIC &&
      entry.reference
    ) {
      map.set(entry.reference, entry);
    }
  }
  return map;
}

/** The annotation on each turn, keyed by turn number parsed from "Turn N". */
export function annotationsByTurn(
  summary: Summary
): Map<number, AnnotationSummaryEntry> {
  const map = new Map<number, AnnotationSummaryEntry>();
  for (const entry of Object.values(summary ?? {})) {
    if (entry.target_type !== ANNOTATION_TARGET_TYPES.TURN || !entry.reference) {
      continue;
    }
    const turn = parseInt(entry.reference.replace(/\D/g, ''), 10);
    if (!isNaN(turn)) map.set(turn, entry);
  }
  return map;
}
