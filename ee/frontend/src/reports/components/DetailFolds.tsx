'use client';

import ReportFold, { ReportFoldRow } from '@/components/reports/ReportFold';
import type { ReportSectionProps } from '@/lib/extension-registries';
import { peopleOf, statsOf, type ReportPerson } from '../types';

function names(people: ReportPerson[]): string {
  return people.length ? people.map(p => p.name).join(', ') : '—';
}

// No FeatureGate: the backend sends this section only when it built or froze it for
// an entitled org, so a published report keeps it after a licence change.
export function PeopleFold({ report }: ReportSectionProps) {
  const people = peopleOf(report);
  if (!people) return null;
  const reviewed = people.reviewers.length
    ? `${names(people.reviewers)} · ${people.verdicts_changed} verdict${people.verdicts_changed === 1 ? '' : 's'} changed`
    : '—';
  return (
    <ReportFold title="Who was involved">
      <ReportFoldRow label="Author">{people.author?.name ?? '—'}</ReportFoldRow>
      <ReportFoldRow label="Ran the tests">
        {names(people.ran_tests)}
      </ReportFoldRow>
      <ReportFoldRow label="Reviewed results">{reviewed}</ReportFoldRow>
    </ReportFold>
  );
}

export function StatsFold({ report }: ReportSectionProps) {
  const stats = statsOf(report);
  if (!stats) return null;
  const times = stats.response_time_ms;
  return (
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
  );
}
