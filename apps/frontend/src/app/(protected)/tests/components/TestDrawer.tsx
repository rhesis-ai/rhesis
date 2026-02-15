'use client';

import React, { useRef } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import CreateTest from './CreateTest';
import UpdateTest from './UpdateTest';

interface TestDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  test?: TestDetail;
  onSuccess?: () => void;
}

export default function TestDrawer({
  open,
  onClose,
  sessionToken,
  test,
  onSuccess,
}: TestDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const submitRef = useRef<(() => Promise<void>) | undefined>(undefined);

  // Get current user from token
  const getCurrentUserId = () => {
    try {
      const [, payloadBase64] = sessionToken.split('.');
      // Add padding if needed
      const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      const paddedBase64 = pad ? base64 + '='.repeat(4 - pad) : base64;

      const payload = JSON.parse(
        Buffer.from(paddedBase64, 'base64').toString('utf-8')
      );
      return payload.user?.id;
    } catch (_err) {
      return undefined;
    }
  };

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
      {test ? (
        <UpdateTest
          sessionToken={sessionToken}
          onSuccess={onSuccess}
          onError={setError}
          submitRef={submitRef}
          test={test}
        />
      ) : (
        <CreateTest
          sessionToken={sessionToken}
          onSuccess={onSuccess}
          onError={setError}
          defaultOwnerId={getCurrentUserId()}
          submitRef={submitRef}
        />
      )}
    </BaseDrawer>
  );
}
