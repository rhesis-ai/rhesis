import React, { useRef } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import CreateTestRun from './CreateTestRun';

interface TestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  selectedTestSetIds: string[];
  onSuccess?: () => void;
}

export default function TestRunDrawer({
  open,
  onClose,
  sessionToken,
  selectedTestSetIds,
  onSuccess,
}: TestRunDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const submitRef = useRef<() => Promise<void>>(undefined);

  const handleSave = async () => {
    try {
      setLoading(true);
      await submitRef.current?.();
      onClose();
    } catch (err) {
      console.error('Error executing test sets:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Execute Test Sets"
      loading={loading}
      error={error}
      onSave={handleSave}
      saveButtonText="Execute now"
    >
      <CreateTestRun
        sessionToken={sessionToken}
        selectedTestSetIds={selectedTestSetIds}
        onSuccess={onSuccess}
        onError={setError}
        submitRef={submitRef}
      />
    </BaseDrawer>
  );
}
