'use client';

import { useCallback, useRef, useState } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import EndpointForm, { type EndpointFormHandle } from './EndpointForm';

interface EndpointCreateDrawerProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  projectId?: string;
}

export default function EndpointCreateDrawer({
  open,
  onClose,
  onCreated,
  projectId,
}: EndpointCreateDrawerProps) {
  const formRef = useRef<EndpointFormHandle>(null);
  const [submitState, setSubmitState] = useState({
    isSubmitting: false,
    canSubmit: false,
  });

  const handleCreated = useCallback(() => {
    onCreated?.();
    onClose();
  }, [onCreated, onClose]);

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Create endpoint"
      width="75%"
      onSave={() => formRef.current?.submit()}
      saveButtonText="Create endpoint"
      saveDataTour="create-endpoint-save"
      saveDisabled={!submitState.canSubmit}
      loading={submitState.isSubmitting}
    >
      {open ? (
        <EndpointForm
          ref={formRef}
          projectId={projectId}
          hideActionBar
          hideProjectSelect
          onCancel={onClose}
          onCreated={handleCreated}
          onSubmitStateChange={setSubmitState}
        />
      ) : null}
    </BaseDrawer>
  );
}
