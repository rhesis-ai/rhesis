import React from 'react';
import EntityCard, {
  type EntityCardFact,
  type EntityCardRelation,
} from '@/components/common/EntityCard';

interface MetricCardProps {
  type?: 'custom-prompt' | 'api-call' | 'custom-code' | 'grading';
  title: string;
  description: string;
  backend?: string;
  metricType?: string;
  scoreType?: string;
  metricScope?: string[];
  usedIn?: string[];
  showUsage?: boolean;
  onDelete?: () => void;
  onClick?: () => void;
}

const capitalize = (value: string) =>
  value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();

/** "Used in A, B", or a count once there are more than two. */
export function usedInRelation(usedIn: string[] = []): EntityCardRelation {
  if (usedIn.length === 0) {
    return {
      key: 'used-in',
      label: 'Not used in any requirement',
      muted: true,
    };
  }
  if (usedIn.length > 2) {
    return { key: 'used-in', label: `Used in ${usedIn.length} requirements` };
  }
  return { key: 'used-in', label: `Used in ${usedIn.join(', ')}` };
}

export default function MetricCard({
  title,
  description,
  backend,
  scoreType,
  metricScope,
  usedIn,
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
      context={backend ? capitalize(backend) : undefined}
      facts={facts}
      relations={showUsage ? [usedInRelation(usedIn)] : []}
      onDelete={onDelete}
      onClick={onClick}
    />
  );
}
