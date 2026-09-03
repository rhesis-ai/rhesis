'use client';

import React, { useMemo, useCallback } from 'react';
import { Grid } from '@mui/material';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UserSettings, UserUpdate } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { useUserScope } from '@/hooks/useIsAuthenticated';
import { userSettingsKeys } from '@/constants/query-keys';
import { validateUrl, normalizeUrl } from '@/utils/validation';
import { SECTION_GRID } from '@/styles/theme-constants';
import { SectionCard } from '@/components/common/SectionCard';
import EditableSection from '@/components/common/EditableSection';
import EditableField from '@/components/common/EditableField';
import ViewField from '@/components/common/ViewField';

interface ProfileFormProps {
  userSettings?: UserSettings;
}

interface ProfileDraft {
  given_name: string;
  family_name: string;
  name: string;
  picture: string;
}

function formatProviderType(providerType?: string): string | null {
  if (!providerType || providerType === 'email') return null;
  const labels: Record<string, string> = {
    google: 'Google',
    github: 'GitHub',
    oidc: 'SSO (OIDC)',
    microsoft: 'Microsoft',
  };
  return labels[providerType] ?? providerType;
}

function draftFromSettings(settings?: UserSettings): ProfileDraft {
  return {
    given_name: settings?.given_name ?? '',
    family_name: settings?.family_name ?? '',
    name: settings?.name ?? '',
    picture: settings?.picture ?? '',
  };
}

export default function ProfileForm({ userSettings }: ProfileFormProps) {
  const router = useRouter();
  const { data: session, update: updateSession } = useSession();
  const queryClient = useQueryClient();
  const userScope = useUserScope();
  const notifications = useNotifications();

  const initialValue = useMemo(
    () => draftFromSettings(userSettings),
    [userSettings]
  );

  const userId = session?.user?.id;
  const providerLabel = formatProviderType(userSettings?.provider_type);

  const handleSave = useCallback(
    async (draft: ProfileDraft) => {
      if (!userId) return;

      const errors: Record<string, string> = {};

      if (draft.picture) {
        const pictureValidation = validateUrl(draft.picture);
        if (!pictureValidation.isValid) {
          errors.picture = pictureValidation.message || '';
        }
      }

      if (Object.keys(errors).length > 0) {
        notifications.show(Object.values(errors)[0], { severity: 'error' });
        throw new Error('validation');
      }

      try {
        const apiFactory = new ApiClientFactory();
        const usersClient = apiFactory.getUsersClient();

        const payload: UserUpdate = {
          given_name: draft.given_name || undefined,
          family_name: draft.family_name || undefined,
          name: draft.name || undefined,
          picture: draft.picture ? normalizeUrl(draft.picture) : undefined,
        };

        const result = await usersClient.updateUser(userId, payload);

        if ('session_token' in result && result.session_token) {
          await updateSession({
            session_token: result.session_token,
          });
        }

        queryClient.invalidateQueries({
          queryKey: userSettingsKeys.all(userScope),
        });

        notifications.show('Profile updated successfully', {
          severity: 'success',
        });

        router.refresh();
      } catch (err: unknown) {
        if (err instanceof Error && err.message === 'validation') {
          throw err;
        }
        notifications.show(
          err instanceof Error ? err.message : 'Failed to update profile',
          { severity: 'error' }
        );
        throw err;
      }
    },
    [userId, notifications, updateSession, queryClient, userScope, router]
  );

  return (
    <>
      <SectionCard title="Account">
        <Grid
          container
          columnSpacing={SECTION_GRID.columnSpacing}
          rowSpacing={SECTION_GRID.rowSpacing}
        >
          <Grid size={{ xs: 12, md: 6 }}>
            <ViewField
              label="Email"
              value={userSettings?.email}
              helperText="Your login email address"
            />
          </Grid>

          {providerLabel && (
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField
                label="Identity provider"
                value={providerLabel}
                helperText="External authentication provider"
              />
            </Grid>
          )}

          <Grid size={{ xs: 12, md: 6 }}>
            <ViewField
              label="Password"
              value={userSettings?.has_password ? 'Set' : 'Not set'}
              helperText={
                userSettings?.has_password
                  ? 'You can sign in with email and password'
                  : 'Set a password to also sign in with email'
              }
            />
          </Grid>
        </Grid>
      </SectionCard>

      <EditableSection
        editable
        title="Personal Information"
        initialValue={initialValue}
        onSave={handleSave}
      >
        {({ draft, setDraft, isEditing }) => (
          <EditableFields
            draft={draft}
            setDraft={setDraft}
            isEditing={isEditing}
          />
        )}
      </EditableSection>
    </>
  );
}

function EditableFields({
  draft,
  setDraft,
  isEditing,
}: {
  draft: ProfileDraft;
  setDraft: (next: ProfileDraft | ((p: ProfileDraft) => ProfileDraft)) => void;
  isEditing: boolean;
}) {
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>(
    {}
  );

  const handleChange =
    (field: keyof ProfileDraft) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setDraft(prev => ({ ...prev, [field]: e.target.value }));
      if (fieldErrors[field]) {
        setFieldErrors(prev => ({ ...prev, [field]: '' }));
      }
    };

  const handleBlur = (field: 'picture') => () => {
    const value = draft[field];
    if (value) {
      const validation = validateUrl(value);
      if (!validation.isValid) {
        setFieldErrors(prev => ({
          ...prev,
          [field]: validation.message || '',
        }));
      }
    }
  };

  return (
    <Grid
      container
      columnSpacing={SECTION_GRID.columnSpacing}
      rowSpacing={SECTION_GRID.rowSpacing}
    >
      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="First Name"
          value={draft.given_name}
          onChange={handleChange('given_name')}
          helperText="Your first name"
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Last Name"
          value={draft.family_name}
          onChange={handleChange('family_name')}
          helperText="Your last name"
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Display Name"
          value={draft.name}
          onChange={handleChange('name')}
          helperText="How your name appears across the platform"
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Picture URL"
          value={draft.picture}
          onChange={handleChange('picture')}
          onBlur={handleBlur('picture')}
          placeholder={isEditing ? 'https://example.com/photo.jpg' : undefined}
          error={isEditing && !!fieldErrors.picture}
          helperText={
            isEditing
              ? fieldErrors.picture || 'URL to your profile picture'
              : 'URL to your profile picture'
          }
        />
      </Grid>
    </Grid>
  );
}
