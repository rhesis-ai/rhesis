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
  const submitRef = useRef<(() => Promise<void>) | undefined>(undefined);

  const handleSave = async () => {
    try {
      setLoading(true);
      await submitRef.current?.();
      onClose();
    } catch (err) {
    } finally {
      setLoading(false);
    }
  };

  const isMultiple = selectedTestSetIds.length > 1;
  const title = isMultiple ? 'Execute Test Sets' : 'Execute Test Set';
  const buttonText = isMultiple ? 'Run Test Sets' : 'Run Test Set';

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      loading={loading}
      error={error}
      onSave={handleSave}
      saveButtonText={buttonText}
    >
      <CreateTestRun
        open={open}
        sessionToken={sessionToken}
        selectedTestSetIds={selectedTestSetIds}
        onSuccess={onSuccess}
        onError={setError}
        submitRef={submitRef}
      />
    </BaseDrawer>
  );
}
