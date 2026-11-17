'use client';

import { FeatureName } from '@/constants/features';
import { FeatureGate } from '@/contexts/FeaturesContext';
import ReportFold, { ReportFoldRow } from '@/components/reports/ReportFold';
import type { ReportSectionProps } from '@/lib/extension-registries';
import { peopleOf, statsOf, type ReportPerson } from '../types';

function names(people: ReportPerson[]): string {
  return people.length ? people.map(p => p.name).join(', ') : '—';
}

export function PeopleFold({ report }: ReportSectionProps) {
  const people = peopleOf(report);
  if (!people) return null;
  const reviewed = people.reviewers.length
    ? `${names(people.reviewers)} · ${people.verdicts_changed} verdict${people.verdicts_changed === 1 ? '' : 's'} changed`
    : '—';
  return (
    <FeatureGate feature={FeatureName.ADVANCED_REPORTS} fallback={null}>
      <ReportFold title="Who was involved">
        <ReportFoldRow label="Author">
          {people.author?.name ?? '—'}
        </ReportFoldRow>
        <ReportFoldRow label="Ran the tests">
          {names(people.ran_tests)}
        </ReportFoldRow>
        <ReportFoldRow label="Reviewed results">{reviewed}</ReportFoldRow>
      </ReportFold>
    </FeatureGate>
  );
}

export function StatsFold({ report }: ReportSectionProps) {
  const stats = statsOf(report);
  if (!stats) return null;
  const times = stats.response_time_ms;
  return (
    <FeatureGate feature={FeatureName.ADVANCED_REPORTS} fallback={null}>
      <ReportFold title="Stats">
        <ReportFoldRow label="Results">
          {stats.results_judged} judged · {stats.results_errored} errored
        </ReportFoldRow>
        <ReportFoldRow label="Response time, mean / p95">
          {times
            ? `${(times.mean / 1000).toFixed(1)} s / ${(times.p95 / 1000).toFixed(1)} s`
            : 'Not measured'}
        </ReportFoldRow>
      </ReportFold>
    </FeatureGate>
  );
}
