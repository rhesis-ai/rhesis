'use client';

import RunDrawer, { type RerunConfig } from '@/components/common/RunDrawer';
import type { BatchRunOutcome } from '@/utils/test-run-batch';

export type { RerunConfig };

interface RerunTestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  data: RerunConfig;
  onSuccess?: () => void;
  onExecuted?: (outcome: BatchRunOutcome) => void;
}

export default function RerunTestRunDrawer({
  open,
  onClose,
  data,
  onSuccess,
  onExecuted,
}: RerunTestRunDrawerProps) {
  return (
    <RunDrawer
      mode="rerunTestRun"
      open={open}
      onClose={onClose}
      data={data}
      onSuccess={onSuccess}
      onExecuted={onExecuted}
    />
  );
}
