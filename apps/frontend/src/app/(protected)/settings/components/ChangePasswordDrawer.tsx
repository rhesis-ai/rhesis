'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { TextField, Alert, Box } from '@mui/material';
import { useRouter } from 'next/navigation';
import { signIn, useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { changePassword } from '@/utils/api-client/auth-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { userSettingsKeys } from '@/constants/query-keys';
import {
  DEFAULT_PASSWORD_POLICY,
  validatePassword,
  validatePasswordConfirmation,
  type PasswordPolicy,
} from '@/utils/validation';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';

interface ChangePasswordDrawerProps {
  open: boolean;
  onClose: () => void;
  hasPassword: boolean;
}

type PasswordField = 'current' | 'new' | 'confirm';

export default function ChangePasswordDrawer({
  open,
  onClose,
  hasPassword,
}: ChangePasswordDrawerProps) {
  const router = useRouter();
  const { update: updateSession } = useSession();
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const notifications = useNotifications();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  // Validation errors belong to one field: shown under it, marked invalid and
  // focused (WCAG 3.3.1). `error` above is for server errors.
  const [fieldError, setFieldError] = useState<{
    field: PasswordField;
    message: string;
  } | null>(null);
  const currentRef = useRef<HTMLInputElement>(null);
  const newRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [passwordPolicy, setPasswordPolicy] = useState<PasswordPolicy | null>(
    null
  );

  useEffect(() => {
    const fetchPolicy = async () => {
      try {
        const res = await fetch('/api/auth-config');
        if (res.ok) {
          const data = await res.json();
          setPasswordPolicy(data.password_policy || null);
        }
      } catch {
        // Fall back to DEFAULT_PASSWORD_POLICY
      }
    };
    fetchPolicy();
  }, []);

  const policy = passwordPolicy ?? DEFAULT_PASSWORD_POLICY;

  const resetForm = useCallback(() => {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError(null);
    setFieldError(null);
    setSaving(false);
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const handleSave = useCallback(async () => {
    setError(null);
    setFieldError(null);
    const fail = (field: PasswordField, message: string) => {
      setFieldError({ field, message });
      const ref = { current: currentRef, new: newRef, confirm: confirmRef }[
        field
      ];
      ref.current?.focus();
    };

    if (hasPassword && !currentPassword) {
      fail('current', 'Current password is required.');
      return;
    }

    const passwordResult = validatePassword(newPassword, policy);
    if (!passwordResult.isValid) {
      fail('new', passwordResult.message ?? 'Invalid password.');
      return;
    }

    const confirmResult = validatePasswordConfirmation(
      newPassword,
      confirmPassword
    );
    if (!confirmResult.isValid) {
      fail('confirm', confirmResult.message ?? 'Passwords do not match.');
      return;
    }

    setSaving(true);
    try {
      const result = await changePassword({
        current_password: hasPassword ? currentPassword : undefined,
        new_password: newPassword,
      });

      // The change revokes every refresh token, including this session's, so
      // swap in the new pair; updateSession alone would only replace the
      // access token.
      let signedIn = false;
      if (result.auth_code) {
        const signInResult = await signIn('credentials', {
          code: result.auth_code,
          redirect: false,
        });
        // A failed exchange comes back as `error`, not a throw.
        signedIn = !signInResult?.error;
      }
      if (!signedIn && result.session_token) {
        await updateSession({ session_token: result.session_token });
      }

      queryClient.invalidateQueries({
        queryKey: userSettingsKeys.all(userScope),
      });
      // The settings page reads `has_password` from a server fetch, so the
      // cache invalidation above doesn't reach it -- without this the card
      // still offers "Set Password" after one was just set.
      router.refresh();

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
    policy,
    updateSession,
    queryClient,
    userScope,
    notifications,
    handleClose,
    router,
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
            inputRef={currentRef}
            error={fieldError?.field === 'current'}
            helperText={
              fieldError?.field === 'current' ? fieldError.message : undefined
            }
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
          inputRef={newRef}
          error={fieldError?.field === 'new'}
          helperText={
            fieldError?.field === 'new'
              ? fieldError.message
              : `Minimum ${policy.min_length} characters`
          }
          autoFocus={!hasPassword}
          sx={drawerOutlinedFieldSx}
        />

        <TextField
          fullWidth
          type="password"
          label="Confirm New Password"
          value={confirmPassword}
          onChange={e => setConfirmPassword(e.target.value)}
          inputRef={confirmRef}
          error={fieldError?.field === 'confirm'}
          helperText={
            fieldError?.field === 'confirm' ? fieldError.message : undefined
          }
          autoComplete="new-password"
          sx={drawerOutlinedFieldSx}
        />
      </Box>
    </BaseDrawer>
  );
}
