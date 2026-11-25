'use client';

import { Box, Chip, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { SectionCard } from '@/components/common/SectionCard';
import { modelKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunScheduleDetail } from '@/utils/api-client/interfaces/test-run-schedule';
import type { UUID } from 'crypto';

/** A model's name, or "Default" when the run uses the project's default. */
function useModelName(id: string | null) {
  const model = useQuery({
    queryKey: modelKeys.detail(id ?? ''),
    queryFn: () =>
      new ApiClientFactory().getModelsClient().getModel(id as UUID),
    enabled: Boolean(id),
    staleTime: Infinity,
  });
  if (!id) return 'Default';
  return model.data?.name ?? (model.isError ? 'Not available' : '…');
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: 'flex', gap: 2, py: 0.75 }}>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ minWidth: theme => theme.spacing(20) }}
      >
        {label}
      </Typography>
      <Box>{children}</Box>
    </Box>
  );
}

const METRICS_SOURCE_LABEL: Record<string, string> = {
  requirement: 'From the requirements of each test',
  test_set: 'Set on the test set',
  execution_time: 'Picked for this schedule',
};

/** What each run uses. Read-only; change the timing in the edit drawer. */
export default function ScheduleConfiguration({
  schedule,
}: {
  schedule: TestRunScheduleDetail;
}) {
  const settings = schedule.run_settings;
  const executionModel = useModelName(settings.execution_model_id);
  const evaluationModel = useModelName(settings.evaluation_model_id);
  const source = settings.metrics_source;

  return (
    <SectionCard
      title="Run settings"
      subtitle="Every run of this schedule uses these settings."
    >
      <Row label="Metrics">
        <Typography variant="body2">
          {source ? (METRICS_SOURCE_LABEL[source] ?? source) : 'Default'}
        </Typography>
        {settings.metrics.length > 0 && (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
            {settings.metrics.map(metric => (
              <Chip key={metric.id} size="small" label={metric.name} />
            ))}
          </Box>
        )}
      </Row>
      <Row label="Execution model">
        <Typography variant="body2">{executionModel}</Typography>
      </Row>
      <Row label="Evaluation model">
        <Typography variant="body2">{evaluationModel}</Typography>
      </Row>
      <Row label="Execution mode">
        <Typography variant="body2">
          {settings.execution_mode ?? 'Default'}
        </Typography>
      </Row>
    </SectionCard>
  );
}
