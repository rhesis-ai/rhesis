'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { Box, MenuItem, Stack, TextField } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import StepNav from '@/components/common/StepNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import RunsStep from './RunsStep';
import RequirementsStep from './RequirementsStep';
import { useEndpointRuns, useRequirementOptions } from './useReportPickerData';

const STEPS = [
  { key: 'setup', label: 'Setup' },
  { key: 'runs', label: 'Runs' },
  { key: 'requirements', label: 'Requirements' },
];
const PAGE_LIMIT = 100;

interface ReportCreateDrawerProps {
  open: boolean;
  onClose: () => void;
}

/** Same shape as the endpoint create drawer: steps on top, the drawer's own footer below. */
function ReportCreateForm({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [step, setStep] = React.useState(0);
  const [title, setTitle] = React.useState('');
  const [endpointId, setEndpointId] = React.useState('');
  const [endpoints, setEndpoints] = React.useState<Endpoint[]>([]);
  const [runIds, setRunIds] = React.useState<string[]>([]);
  const [requirementIds, setRequirementIds] = React.useState<string[]>([]);
  const [pickedForRuns, setPickedForRuns] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    new ApiClientFactory()
      .getEndpointsClient()
      .getEndpoints({ skip: 0, limit: PAGE_LIMIT })
      .then(page => setEndpoints(page.data))
      .catch(() => setError('Failed to load endpoints'));
  }, []);

  // A new endpoint means none of the picked runs belong to it any more.
  React.useEffect(() => setRunIds([]), [endpointId]);

  const runsData = useEndpointRuns(endpointId);
  const {
    requirements,
    tested,
    loading: requirementsLoading,
    failed: requirementsFailed,
    ready: requirementsReady,
  } = useRequirementOptions(runIds, step === 2);

  // Reaching the last step with a new set of runs picks what those runs tested.
  const runKey = [...runIds].sort().join(',');
  React.useEffect(() => {
    if (step !== 2 || !requirementsReady || pickedForRuns === runKey) return;
    setRequirementIds([...tested]);
    setPickedForRuns(runKey);
  }, [step, requirementsReady, tested, runKey, pickedForRuns]);

  const loadError =
    error ??
    (runsData.failed ? 'Failed to load test runs' : null) ??
    (requirementsFailed ? 'Failed to load requirements' : null);

  const stepValid = [
    title.trim().length > 0 && endpointId.length > 0,
    runIds.length > 0,
    !requirementsLoading,
  ];
  const firstInvalid = stepValid.findIndex(valid => !valid);
  const maxReachable = firstInvalid === -1 ? STEPS.length - 1 : firstInvalid;
  const isFirst = step === 0;
  const isLast = step === STEPS.length - 1;

  const create = async () => {
    setSaving(true);
    setError(null);
    try {
      const report = await new ApiClientFactory()
        .getReportsClient()
        .createReport({
          title: title.trim(),
          endpoint_id: endpointId,
          test_run_ids: runIds,
          requirement_ids: requirementIds,
        });
      router.push(`/reports/${report.id}`);
    } catch {
      setError('Failed to create the report');
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open
      onClose={onClose}
      title="Create report"
      width="75%"
      onSave={isLast ? create : () => setStep(step + 1)}
      saveButtonText={isLast ? 'Create draft' : 'Next'}
      saveDisabled={!stepValid[step]}
      closeButtonText={isFirst ? 'Cancel' : ''}
      onBack={isFirst ? undefined : () => setStep(step - 1)}
      loading={saving}
      error={loadError ?? undefined}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        <Box>
          <StepNav
            steps={STEPS}
            activeIndex={step}
            maxReachableIndex={maxReachable}
            onChange={setStep}
            aria-label="Report creation steps"
          />
        </Box>
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflow: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <DetailTabPanel value={step} index={0} prefix="report">
            <Stack spacing={3}>
              <TextField
                label="Title"
                placeholder="Release 2.4"
                value={title}
                onChange={e => setTitle(e.target.value)}
                required
                fullWidth
                inputProps={{ maxLength: 200 }}
              />
              <TextField
                select
                label="Endpoint"
                value={endpointId}
                onChange={e => setEndpointId(e.target.value)}
                required
                fullWidth
                helperText="One endpoint per report. Its config is saved when you publish."
              >
                {endpoints.map(endpoint => (
                  <MenuItem key={endpoint.id} value={endpoint.id}>
                    {endpoint.name}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          </DetailTabPanel>
          <DetailTabPanel value={step} index={1} prefix="report">
            <RunsStep
              runs={runsData.runs}
              loading={runsData.loading}
              selected={runIds}
              onChange={setRunIds}
            />
          </DetailTabPanel>
          <DetailTabPanel value={step} index={2} prefix="report">
            <RequirementsStep
              requirements={requirements}
              loading={requirementsLoading}
              tested={tested}
              selected={requirementIds}
              onChange={setRequirementIds}
            />
          </DetailTabPanel>
        </Box>
      </Box>
    </BaseDrawer>
  );
}

export default function ReportCreateDrawer({
  open,
  onClose,
}: ReportCreateDrawerProps) {
  // Mounted only while open, so each opening starts from a clean form.
  return open ? <ReportCreateForm onClose={onClose} /> : null;
}
