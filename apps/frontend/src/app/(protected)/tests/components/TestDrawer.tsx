'use client';

import React, { useRef } from 'react';
import { useSession } from 'next-auth/react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import CreateTest from './CreateTest';
import UpdateTest from './UpdateTest';

interface TestDrawerProps {
  open: boolean;
  onClose: () => void;
  test?: TestDetail;
  onSuccess?: () => void;
}

export default function TestDrawer({
  open,
  onClose,
  test,
  onSuccess,
}: TestDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const submitRef = useRef<(() => Promise<void>) | undefined>(undefined);

  // Current user from the session (the access token never reaches the
  // browser, so there is no JWT to decode client-side).
  const { data: session } = useSession();
  const getCurrentUserId = () =>
    session?.user?.id as
      `${string}-${string}-${string}-${string}-${string}` | undefined;

  const handleSave = async () => {
    try {
      setLoading(true);
      await submitRef.current?.();
      onClose();
    } catch (_err) {
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={test ? 'Edit Test' : 'New Test'}
      loading={loading}
      error={error}
      onSave={handleSave}
    >
      {open &&
        (test ? (
          <UpdateTest
            onSuccess={onSuccess}
            onError={setError}
            submitRef={submitRef}
            test={test}
          />
        ) : (
          <CreateTest
            onSuccess={onSuccess}
            onError={setError}
            defaultOwnerId={getCurrentUserId()}
            submitRef={submitRef}
          />
        ))}
    </BaseDrawer>
  );
}
