/**
 * Registry of extra sections and columns on the report page.
 *
 * Core renders the light report on its own: summary, requirements, runs. EE
 * adds the By impact section, the impact column, Who was involved, Stats and
 * the audit trail by registering them here from its bootstrap.
 *
 * Slots, top to bottom: `after-summary` (below the summary), `details` (the
 * folded blocks at the end), `footer` (beside the snapshot hash). A column is
 * added to the requirements tree.
 *
 * An entry with a `sectionKey` renders only when the report carries that
 * backend section (`report.sections[sectionKey]`), so it shows exactly what
 * the backend built or froze. Components still wrap themselves in
 * `<FeatureGate>`; core does not.
 *
 * Usage from EE
 * -------------
 * ```ts
 * import { registerReportSection } from '@/lib/extension-registries';
 *
 * registerReportSection({
 *   id: 'by-impact',
 *   slot: 'after-summary',
 *   order: 10,
 *   sectionKey: 'by_impact',
 *   component: ByImpactSection,
 * });
 * ```
 */

import type { ComponentType } from 'react';
import type {
  ReportDetail,
  ReportRequirementRow,
} from '@/utils/api-client/interfaces/report';

export type ReportSectionSlot = 'after-summary' | 'details' | 'footer';

export interface ReportSectionProps {
  report: ReportDetail;
}

export interface ReportSection {
  /** Unique identifier (de-duplication and React keys). */
  id: string;
  slot: ReportSectionSlot;
  /** Sort order within the slot. */
  order: number;
  /** Render only when `report.sections` has this key. */
  sectionKey?: string;
  component: ComponentType<ReportSectionProps>;
}

export interface ReportColumnCellProps {
  report: ReportDetail;
  row: ReportRequirementRow;
}

export interface ReportRequirementColumn {
  id: string;
  order: number;
  header: string;
  /** The column shows only when `report.sections` has this key. */
  sectionKey: string;
  cell: ComponentType<ReportColumnCellProps>;
}

const _sections: ReportSection[] = [];
const _columns: ReportRequirementColumn[] = [];
let _sectionCache: readonly ReportSection[] | null = null;
let _columnCache: readonly ReportRequirementColumn[] | null = null;

/** Idempotent: re-registering the same `id` is a no-op. */
export function registerReportSection(section: ReportSection): void {
  if (_sections.some(s => s.id === section.id)) return;
  _sections.push(section);
  _sectionCache = null;
}

/** Idempotent: re-registering the same `id` is a no-op. */
export function registerReportRequirementColumn(
  column: ReportRequirementColumn
): void {
  if (_columns.some(c => c.id === column.id)) return;
  _columns.push(column);
  _columnCache = null;
}

/** Every registered section, sorted by `order`. Frozen and cached. */
export function getReportSections(): readonly ReportSection[] {
  if (_sectionCache === null) {
    _sectionCache = Object.freeze(
      [..._sections].sort((a, b) => a.order - b.order)
    );
  }
  return _sectionCache;
}

/** Every registered column, sorted by `order`. Frozen and cached. */
export function getReportRequirementColumns(): readonly ReportRequirementColumn[] {
  if (_columnCache === null) {
    _columnCache = Object.freeze(
      [..._columns].sort((a, b) => a.order - b.order)
    );
  }
  return _columnCache;
}

/** Reset the registry. Intended for tests only. */
export function resetReportSections(): void {
  _sections.length = 0;
  _columns.length = 0;
  _sectionCache = null;
  _columnCache = null;
}
