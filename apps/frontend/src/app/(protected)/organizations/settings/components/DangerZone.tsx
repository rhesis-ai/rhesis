'use client';

import * as React from 'react';
import { Typography, Button } from '@mui/material';
import { useState } from 'react';
import { signOut } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';

interface DangerZoneProps {
  organization: Organization;
  sessionToken: string;
}

export default function DangerZone({
  organization,
  sessionToken,
}: DangerZoneProps) {
  const notifications = useNotifications();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  const handleOpenDialog = () => {
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    if (!isLeaving) {
      setDialogOpen(false);
    }
  };

  const handleLeaveOrganization = async () => {
    setIsLeaving(true);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const usersClient = apiFactory.getUsersClient();

      // Call the leave organization endpoint
      await usersClient.leaveOrganization();

      // Close the dialog
      setDialogOpen(false);

      // Show success message
      notifications.show(`You have left ${organization.name}`, {
        severity: 'success',
      });

      // Sign out and redirect to login
      await signOut({
        callbackUrl: `/auth/signin?message=${encodeURIComponent(`You have successfully left ${organization.name}. You can now create a new organization or accept an invitation.`)}`,
      });
    } catch (err: any) {
      notifications.show(err.message || 'Failed to leave organization', {
        severity: 'error',
      });
      setIsLeaving(false);
    }
  };

  return (
    <>
      <Typography variant="h6" color="error" gutterBottom>
        Danger Zone
      </Typography>
      <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
        Leaving the organization will remove your access to all projects, tests,
        and data. Your contributions will remain, but you will no longer be able
        to access them.
      </Typography>
      <Button variant="outlined" color="error" onClick={handleOpenDialog}>
        Leave Organization
      </Button>

      <DeleteModal
        open={dialogOpen}
        onClose={handleCloseDialog}
        onConfirm={handleLeaveOrganization}
        isLoading={isLeaving}
        title="Leave Organization"
        message={
          <>
            Leaving <strong>{organization.name}</strong> will remove your access
            to all organization data and projects. You will need to be
            re-invited to rejoin this organization. Your contributions will
            remain in the organization.
          </>
        }
        confirmButtonText={isLeaving ? 'Leaving...' : 'Leave Organization'}
        requireConfirmation
        confirmationText={organization.name}
        confirmationLabel="To confirm, please type the organization name:"
        warningMessage="This action is irreversible."
        showTopBorder
      />
    </>
  );
}
