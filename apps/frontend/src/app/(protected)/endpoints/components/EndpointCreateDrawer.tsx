'use client';

import { useCallback, useRef, useState } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { QuotaResource } from '@/constants/quota';
import { useQuotaGate } from '@/hooks/useQuotaGate';
import EndpointForm, {
  type EndpointFormHandle,
  type EndpointFormSubmitState,
} from './EndpointForm';

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
  const [submitState, setSubmitState] = useState<EndpointFormSubmitState>({
    isSubmitting: false,
    canAdvance: false,
    isLastStep: false,
    isFirstStep: true,
    isTested: false,
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
      title="Create REST endpoint"
      width="75%"
      onSave={() => formRef.current?.advance()}
      // Steps 2-4 go back step by step; only the first step offers Cancel.
      closeButtonText={submitState.isFirstStep ? 'Cancel' : ''}
      onBack={
        submitState.isFirstStep ? undefined : () => formRef.current?.back()
      }
      saveButtonText={
        !submitState.isLastStep
          ? 'Next'
          : submitState.isTested
            ? 'Create endpoint'
            : 'Create without test'
      }
      saveDataTour={submitState.isLastStep ? 'create-endpoint-save' : undefined}
      saveDisabled={
        !submitState.canAdvance ||
        (submitState.isLastStep && endpointQuota.exhausted)
      }
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
          hideProjectSelect
          onCreated={handleCreated}
          onSubmitStateChange={setSubmitState}
        />
      ) : null}
    </BaseDrawer>
  );
}
