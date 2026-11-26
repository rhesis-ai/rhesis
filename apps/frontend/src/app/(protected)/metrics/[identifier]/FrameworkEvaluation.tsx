'use client';

import { Link, Typography } from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import VisuallyHidden from '@/components/common/VisuallyHidden';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import {
  frameworkInfo,
  isFrameworkPlaceholder,
} from '@/utils/metric-framework';
import InfoRow from './MetricInfoRow';

function inputsNeeded(metric: MetricDetail): string {
  const needs = [
    metric.context_required && 'retrieved context',
    metric.ground_truth_required && 'a ground truth',
  ].filter(Boolean);
  return needs.length > 0
    ? `Input, output and ${needs.join(' and ')}`
    : 'Input and output';
}

/**
 * The Evaluation Process card for a framework metric. The framework owns the
 * prompt and scoring, so this says which framework and implementation run it
 * and what it needs, in place of prompt fields it never fills in.
 */
export default function FrameworkEvaluation({
  metric,
}: {
  metric: MetricDetail;
}) {
  const { label, docsUrl } = frameworkInfo(metric);
  // Garak metrics name their detector here; DeepEval ones hold a marker.
  const detector =
    metric.evaluation_prompt &&
    !isFrameworkPlaceholder(metric.evaluation_prompt)
      ? metric.evaluation_prompt
      : undefined;

  return (
    <SectionCard title="Evaluation Process">
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Defined by {label}, which runs the evaluation, so this metric can&apos;t
        be edited here.{' '}
        <Link href={docsUrl} target="_blank" rel="noopener noreferrer">
          About {label} metrics
          <VisuallyHidden component="span">
            {' '}
            (opens in a new tab)
          </VisuallyHidden>
        </Link>
      </Typography>

      <InfoRow label="Framework">
        <Typography>{label}</Typography>
      </InfoRow>

      {metric.class_name && (
        <InfoRow label="Implementation">
          <Typography sx={{ fontFamily: 'monospace' }}>
            {metric.class_name}
          </Typography>
        </InfoRow>
      )}

      {detector && (
        <InfoRow label="Detector">
          <Typography sx={{ fontFamily: 'monospace', wordBreak: 'break-word' }}>
            {detector}
          </Typography>
        </InfoRow>
      )}

      <InfoRow label="Evaluates">
        <Typography>{inputsNeeded(metric)}</Typography>
      </InfoRow>
    </SectionCard>
  );
}
