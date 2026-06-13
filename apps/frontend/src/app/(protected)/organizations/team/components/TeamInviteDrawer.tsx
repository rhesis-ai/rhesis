'use client';

import * as React from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import TeamInviteForm from './TeamInviteForm';

interface TeamInviteDrawerProps {
  open: boolean;
  onClose: () => void;
  onInvitesSent?: (emails: string[]) => void;
  disableDuringTour?: boolean;
}

export default function TeamInviteDrawer({
  open,
  onClose,
  onInvitesSent,
  disableDuringTour = false,
}: TeamInviteDrawerProps) {
  const formRef = React.useRef<HTMLFormElement>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleInvitesSent = (emails: string[]) => {
    onInvitesSent?.(emails);
    if (emails.length > 0) {
      onClose();
    }
  };

  const handleSave = () => {
    formRef.current?.requestSubmit();
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Invite team members"
      onSave={handleSave}
      saveButtonText="Send Invitations"
      saveDataTour="send-invites-button"
      loading={isSubmitting}
      saveDisabled={disableDuringTour}
    >
      <TeamInviteForm
        ref={formRef}
        embedded
        onInvitesSent={handleInvitesSent}
        disableDuringTour={disableDuringTour}
        onSubmittingChange={setIsSubmitting}
      />
    </BaseDrawer>
  );
}
