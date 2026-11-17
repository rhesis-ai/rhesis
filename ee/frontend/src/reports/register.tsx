/**
 * Enterprise report sections, plugged into core's `report-sections` registry.
 *
 * By impact, the impact column, Who was involved and Stats render when the backend
 * sent their section (`sectionKey`); the backend only builds them for orgs with
 * `FeatureName.ADVANCED_REPORTS`, and a published report keeps them frozen. The
 * audit trail and the footer line read live data, so they wrap themselves in a
 * `FeatureGate` for `FeatureName.AUDIT_LOG` with no fallback: Community shows no
 * teaser.
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
