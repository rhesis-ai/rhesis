'use client';

import RunDrawer, { type RerunConfig } from '@/components/common/RunDrawer';

export type { RerunConfig };

interface RerunTestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  data: RerunConfig;
  onSuccess?: () => void;
}

export default function RerunTestRunDrawer({
  open,
  onClose,
  sessionToken,
  data,
  onSuccess,
}: RerunTestRunDrawerProps) {
  return (
    <RunDrawer
      mode="rerunTestRun"
      open={open}
      onClose={onClose}
      sessionToken={sessionToken}
      data={data}
      onSuccess={onSuccess}
    />
  );
}
