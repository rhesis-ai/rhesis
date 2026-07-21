'use client';

import BaseDrawer from '@/components/common/BaseDrawer';
import OwaspGenerateForm, {
  type OwaspGenerateFooterState,
} from './OwaspGenerateForm';
import React from 'react';

/** Match GarakImportDrawer width for standalone OWASP use. */
const SECURITY_DRAWER_WIDTH = 680;

interface OwaspGenerateDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (taskIds: string[]) => void;
}

/** Standalone OWASP drawer — prefer the Garak drawer source dropdown for new UI. */
export default function OwaspGenerateDrawer({
  open,
  onClose,
  sessionToken,
  onSuccess,
}: OwaspGenerateDrawerProps) {
  const [footer, setFooter] = React.useState<OwaspGenerateFooterState | null>(
    null
  );

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Generate from OWASP"
      width={SECURITY_DRAWER_WIDTH}
      closeButtonText={footer?.closeButtonText ?? 'Cancel'}
      loading={footer?.loading ?? false}
      onSave={footer?.onSave}
      saveDisabled={footer?.saveDisabled ?? true}
      saveButtonText={footer?.saveButtonText ?? 'Generate'}
    >
      <OwaspGenerateForm
        active={open}
        sessionToken={sessionToken}
        onSuccess={onSuccess}
        onFooterChange={setFooter}
      />
    </BaseDrawer>
  );
}
