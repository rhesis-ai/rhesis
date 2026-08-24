'use client';

import { useCallback, useRef, useState } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { QuotaResource } from '@/constants/quota';
import { useQuotaGate } from '@/hooks/useQuotaGate';
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

  const endpointQuota = useQuotaGate(QuotaResource.ENDPOINTS);

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
      saveDisabled={!submitState.canSubmit || endpointQuota.exhausted}
      loading={submitState.isSubmitting}
      // The gate goes on the submit, never on the FAB that opens this drawer:
      // a disabled FAB leaves the explanation nowhere to live. The form's own
      // 402 handling covers the case where usage changes mid-edit.
      error={endpointQuota.notice}
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
