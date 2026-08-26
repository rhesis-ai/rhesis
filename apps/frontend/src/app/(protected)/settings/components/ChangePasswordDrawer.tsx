'use client';

import React, { useState, useCallback } from 'react';
import { TextField, Alert, Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { changePassword } from '@/utils/api-client/auth-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { userSettingsKeys } from '@/constants/query-keys';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';

const MIN_PASSWORD_LENGTH = 12;

interface ChangePasswordDrawerProps {
  open: boolean;
  onClose: () => void;
  hasPassword: boolean;
}

export default function ChangePasswordDrawer({
  open,
  onClose,
  hasPassword,
}: ChangePasswordDrawerProps) {
  const { update: updateSession } = useSession();
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const notifications = useNotifications();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const resetForm = useCallback(() => {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError(null);
    setSaving(false);
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const handleSave = useCallback(async () => {
    setError(null);

    if (hasPassword && !currentPassword) {
      setError('Current password is required.');
      return;
    }

    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.');
      return;
    }

    setSaving(true);
    try {
      const result = await changePassword({
        current_password: hasPassword ? currentPassword : undefined,
        new_password: newPassword,
      });

      if (result.session_token) {
        await updateSession({ session_token: result.session_token });
      }

      queryClient.invalidateQueries({
        queryKey: userSettingsKeys.all(userScope),
      });

      notifications.show(
        hasPassword
          ? 'Password changed successfully.'
          : 'Password set successfully.',
        { severity: 'success' }
      );

      handleClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to update password.';
      setError(message);
    } finally {
      setSaving(false);
    }
  }, [
    hasPassword,
    currentPassword,
    newPassword,
    confirmPassword,
    updateSession,
    queryClient,
    userScope,
    notifications,
    handleClose,
  ]);

  const canSave =
    newPassword.length > 0 &&
    confirmPassword.length > 0 &&
    (!hasPassword || currentPassword.length > 0);

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title={hasPassword ? 'Change Password' : 'Set Password'}
      onSave={handleSave}
      saveDisabled={!canSave}
      loading={saving}
      saveButtonText={hasPassword ? 'Change Password' : 'Set Password'}
    >
      <Box sx={drawerFieldsSx}>
        {error && <Alert severity="error">{error}</Alert>}

        {hasPassword && (
          <TextField
            fullWidth
            type="password"
            label="Current Password"
            value={currentPassword}
            onChange={e => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            autoFocus
            sx={drawerOutlinedFieldSx}
          />
        )}

        <TextField
          fullWidth
          type="password"
          label="New Password"
          value={newPassword}
          onChange={e => setNewPassword(e.target.value)}
          autoComplete="new-password"
          helperText={`Minimum ${MIN_PASSWORD_LENGTH} characters`}
          autoFocus={!hasPassword}
          sx={drawerOutlinedFieldSx}
        />

        <TextField
          fullWidth
          type="password"
          label="Confirm New Password"
          value={confirmPassword}
          onChange={e => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
          sx={drawerOutlinedFieldSx}
        />
      </Box>
    </BaseDrawer>
  );
}
