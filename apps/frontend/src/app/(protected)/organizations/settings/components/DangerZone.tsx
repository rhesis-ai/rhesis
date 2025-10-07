'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  CircularProgress,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { useNotifications } from '@/components/common/NotificationContext';

interface DangerZoneProps {
  organization: Organization;
  sessionToken: string;
}

export default function DangerZone({
  organization,
  sessionToken,
}: DangerZoneProps) {
  const { data: session } = useSession();
  const router = useRouter();
  const notifications = useNotifications();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [isLeaving, setIsLeaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOpenDialog = () => {
    setDialogOpen(true);
    setConfirmText('');
    setError(null);
  };

  const handleCloseDialog = () => {
    if (!isLeaving) {
      setDialogOpen(false);
      setConfirmText('');
      setError(null);
    }
  };

  const handleLeaveOrganization = async () => {
    // Validate confirmation text
    if (confirmText !== organization.name) {
      setError(`Please type "${organization.name}" exactly to confirm`);
      return;
    }

    setIsLeaving(true);
    setError(null);

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
      // The signOut will clear the session and redirect to the login page
      await signOut({
        callbackUrl: `/auth/signin?message=${encodeURIComponent(`You have successfully left ${organization.name}. You can now create a new organization or accept an invitation.`)}`,
      });
    } catch (err: any) {
      console.error('Error leaving organization:', err);
      setError(err.message || 'Failed to leave organization');
      setIsLeaving(false);
    }
  };

  return (
    <>
      <Box
        sx={{
          border: '2px solid',
          borderColor: 'error.main',
          borderRadius: theme => theme.shape.borderRadius,
          p: 3,
          backgroundColor: theme =>
            theme.palette.mode === 'dark'
              ? alpha(theme.palette.error.main, 0.08)
              : alpha(theme.palette.error.main, 0.04),
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <WarningAmberIcon color="error" sx={{ mt: 0.5 }} />
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6" color="error" gutterBottom>
              Danger Zone
            </Typography>
            <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
              Leaving the organization will remove your access to all projects,
              tests, and data. Your contributions will remain, but you will no
              longer be able to access them.
            </Typography>
            <Button
              variant="outlined"
              color="error"
              onClick={handleOpenDialog}
              sx={{
                borderWidth: 2,
                '&:hover': {
                  borderWidth: 2,
                  backgroundColor: 'error.main',
                  color: 'white',
                },
              }}
            >
              Leave Organization
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Confirmation Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderTop: '4px solid',
            borderColor: 'error.main',
          },
        }}
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WarningAmberIcon color="error" />
            <Typography variant="h6">Leave Organization</Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 3 }}>
            <Typography variant="body2" fontWeight="bold" gutterBottom>
              This action is irreversible. You will:
            </Typography>
            <Box
              component="ul"
              sx={{
                m: theme => theme.spacing(1, 0),
                pl: theme => theme.spacing(2.5),
              }}
            >
              <li>Lose access to all organization data and projects</li>
              <li>Need to be re-invited to rejoin this organization</li>
              <li>Go through the onboarding process again</li>
            </Box>
            <Typography variant="body2" fontWeight="bold" sx={{ mt: 1 }}>
              Your contributions (tests, prompts, etc.) will remain in the
              organization.
            </Typography>
          </Alert>

          <Typography variant="body2" sx={{ mb: 2 }}>
            To confirm, please type the organization name:{' '}
            <Typography component="span" fontWeight="bold">
              {organization.name}
            </Typography>
          </Typography>

          <TextField
            fullWidth
            placeholder={`Type "${organization.name}" to confirm`}
            value={confirmText}
            onChange={e => setConfirmText(e.target.value)}
            disabled={isLeaving}
            error={!!error}
            helperText={error}
            autoFocus
            sx={{ mb: 2 }}
          />

          {isLeaving && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Leaving organization...
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={handleCloseDialog} disabled={isLeaving}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleLeaveOrganization}
            disabled={isLeaving || confirmText !== organization.name}
          >
            {isLeaving ? 'Leaving...' : 'Leave Organization'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
