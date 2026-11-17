/**
 * Enterprise report sections, plugged into core's `report-sections` registry.
 *
 * By impact, the impact column, Who was involved and Stats render only when the
 * backend sent their section (`sectionKey`) and the org has
 * `FeatureName.ADVANCED_REPORTS`. The audit trail and the footer line read the
 * live audit trail and need `FeatureName.AUDIT_LOG`. Each wraps itself in a
 * `FeatureGate` with no fallback: Community shows no teaser.
 */

import {
  registerReportRequirementColumn,
  registerReportSection,
} from '@/lib/extension-registries';
import { ByImpactSection, ImpactCell } from './components/ByImpact';
import { PeopleFold, StatsFold } from './components/DetailFolds';
import { AuditFooterLine, AuditTrailFold } from './components/AuditTrail';

export function registerReports(): void {
  registerReportSection({
    id: 'by-impact',
    slot: 'after-summary',
    order: 10,
    sectionKey: 'by_impact',
    component: ByImpactSection,
  });
  registerReportRequirementColumn({
    id: 'impact',
    order: 10,
    header: 'Impact',
    sectionKey: 'by_impact',
    cell: ImpactCell,
  });
  registerReportSection({
    id: 'people',
    slot: 'details',
    order: 10,
    sectionKey: 'people',
    component: PeopleFold,
  });
  registerReportSection({
    id: 'stats',
    slot: 'details',
    order: 20,
    sectionKey: 'stats',
    component: StatsFold,
  });
  registerReportSection({
    id: 'audit-trail',
    slot: 'details',
    order: 30,
    component: AuditTrailFold,
  });
  registerReportSection({
    id: 'audit-footer',
    slot: 'footer',
    order: 10,
    component: AuditFooterLine,
  });
}
