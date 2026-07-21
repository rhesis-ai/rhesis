'use client';

import RunDrawer, { type RerunConfig } from '@/components/common/RunDrawer';

export type { RerunConfig };

interface RerunTestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  data: RerunConfig;
  onSuccess?: () => void;
}

export default function RerunTestRunDrawer({
  open,
  onClose,
  data,
  onSuccess,
}: RerunTestRunDrawerProps) {
  return (
    <RunDrawer
      mode="rerunTestRun"
      open={open}
      onClose={onClose}
      data={data}
      onSuccess={onSuccess}
    />
  );
}
