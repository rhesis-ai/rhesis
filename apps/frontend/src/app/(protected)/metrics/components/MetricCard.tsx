import React from 'react';
import EntityCard, {
  skeletonCardKeys,
  type EntityCardFact,
  type EntityCardRelation,
} from '@/components/common/EntityCard';
import { TEST_TYPES } from '@/constants/test-types';
import { RequirementsIcon, TuneIcon } from '@/components/icons';
import { backendLabel } from './list';

interface MetricCardProps {
  type?: 'custom-prompt' | 'api-call' | 'custom-code' | 'grading';
  title: string;
  description: string;
  backend?: string;
  metricType?: string;
  scoreType?: string;
  metricScope?: string[];
  usedIn?: string[];
  /** Custom metrics only; omitted for metrics that can't be tuned. */
  tuningCases?: number;
  showUsage?: boolean;
  onDelete?: () => void;
  onClick?: () => void;
}

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();

/** Requirement icon + count, like the requirement card's relations; names in the tooltip. */
export function usedInRelation(usedIn: string[] = []): EntityCardRelation {
  const count = usedIn.length;
  const label = count === 1 ? 'requirement' : 'requirements';
  return {
    key: 'used-in',
    label,
    count,
    icon: <RequirementsIcon />,
    tooltip:
      count > 0 ? `${count} ${label}: ${usedIn.join(', ')}` : `0 ${label}`,
  };
}

/** Tuning icon + count, same style as the requirements relation. */
export function tuningCasesRelation(count: number): EntityCardRelation {
  return {
    key: 'tuning-cases',
    label: count === 1 ? 'tuning case' : 'tuning cases',
    count,
    icon: <TuneIcon />,
  };
}

export default function MetricCard({
  title,
  description,
  backend,
  scoreType,
  metricScope,
  usedIn,
  tuningCases,
  showUsage = false,
  onDelete,
  onClick,
}: MetricCardProps) {
  const facts: EntityCardFact[] = [];
  if (scoreType) {
    facts.push({
      key: 'score-type',
      kind: 'type',
      label: capitalize(scoreType),
    });
  }
  (metricScope ?? []).forEach(scope => {
    facts.push({ key: `scope-${scope}`, kind: 'plain', label: scope });
  });

  return (
    <EntityCard
      title={title}
      description={description}
      context={backend ? backendLabel(backend) : undefined}
      facts={facts}
      relations={
        showUsage
          ? [
              usedInRelation(usedIn),
              ...(tuningCases === undefined
                ? []
                : [tuningCasesRelation(tuningCases)]),
            ]
          : []
      }
      onDelete={onDelete}
      onClick={onClick}
    />
  );
}

/** A loading view's cards: the real card in skeleton mode, with typical values. */
export function MetricCardPlaceholders() {
  return (
    <>
      {skeletonCardKeys.map(key => (
        <MetricCard
          key={key}
          title="Answer relevancy"
          description=""
          backend="rhesis"
          scoreType="numeric"
          metricScope={[TEST_TYPES.SINGLE_TURN]}
          usedIn={[]}
          showUsage
        />
      ))}
    </>
  );
}
