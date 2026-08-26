'use client';

import React, { useMemo, useState, useCallback } from 'react';
import { Box, Grid, IconButton, Tooltip } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateUrl, normalizeUrl } from '@/utils/validation';
import { SECTION_GRID } from '@/styles/theme-constants';
import EditableSection from '@/components/common/EditableSection';
import EditableField from '@/components/common/EditableField';
import ViewField from '@/components/common/ViewField';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface OrganizationDetailsFormProps {
  organization: Organization;
  onUpdate: () => void;
}

interface DetailsDraft {
  name: string;
  display_name: string;
  description: string;
  website: string;
  logo_url: string;
}

function draftFromOrganization(org: Organization): DetailsDraft {
  return {
    name: org.name || '',
    display_name: org.display_name || '',
    description: org.description || '',
    website: org.website || '',
    logo_url: org.logo_url || '',
  };
}

export default function OrganizationDetailsForm({
  organization,
  onUpdate,
}: OrganizationDetailsFormProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const initialValue = useMemo(
    () => draftFromOrganization(organization),
    [organization]
  );

  const handleSave = async (draft: DetailsDraft) => {
    const errors: Record<string, string> = {};

    if (draft.website) {
      const websiteValidation = validateUrl(draft.website);
      if (!websiteValidation.isValid) {
        errors.website = websiteValidation.message || '';
      }
    }

    if (draft.logo_url) {
      const logoValidation = validateUrl(draft.logo_url);
      if (!logoValidation.isValid) {
        errors.logo_url = logoValidation.message || '';
      }
    }

    if (Object.keys(errors).length > 0) {
      notifications.show(Object.values(errors)[0], { severity: 'error' });
      throw new Error('validation');
    }

    try {
      const apiFactory = new ApiClientFactory();
      const organizationsClient = apiFactory.getOrganizationsClient();

      const website = draft.website ? normalizeUrl(draft.website) : undefined;
      const logo_url = draft.logo_url
        ? normalizeUrl(draft.logo_url)
        : undefined;

      await organizationsClient.updateOrganization(organization.id, {
        name: draft.name,
        display_name: draft.display_name || undefined,
        description: draft.description || undefined,
        website,
        logo_url,
      });

      notifications.show('Organization details updated successfully', {
        severity: 'success',
      });

      router.refresh();
      onUpdate();
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'validation') {
        throw err;
      }
      notifications.show(
        err instanceof Error
          ? err.message
          : 'Failed to update organization details',
        { severity: 'error' }
      );
      throw err;
    }
  };

  return (
    <EditableSection
      editable={canUpdateOrg}
      title="Basic Information"
      initialValue={initialValue}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <DetailsFields
          organizationId={organization.id}
          draft={draft}
          setDraft={setDraft}
          isEditing={isEditing}
        />
      )}
    </EditableSection>
  );
}

function DetailsFields({
  organizationId,
  draft,
  setDraft,
  isEditing,
}: {
  organizationId: string;
  draft: DetailsDraft;
  setDraft: (next: DetailsDraft | ((p: DetailsDraft) => DetailsDraft)) => void;
  isEditing: boolean;
}) {
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>(
    {}
  );
  const [copied, setCopied] = useState(false);

  const notifications = useNotifications();

  const handleCopyId = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(organizationId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_err) {
      notifications.show('Failed to copy organization ID', {
        severity: 'error',
      });
    }
  }, [organizationId, notifications]);

  const handleChange =
    (field: keyof DetailsDraft) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setDraft(prev => ({ ...prev, [field]: e.target.value }));
      if (fieldErrors[field]) {
        setFieldErrors(prev => ({ ...prev, [field]: '' }));
      }
    };

  const handleBlur = (field: 'website' | 'logo_url') => () => {
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
      <Grid size={12}>
        <ViewField
          label="Organization ID"
          helperText="Used for API integrations and support requests"
          bgcolor="transparent"
        >
          <Box
            sx={{
              fontFamily: 'monospace',
              fontSize: theme => theme.typography.body2.fontSize,
              letterSpacing: '0.01em',
              color: theme => theme.palette.greyscale.body,
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
            }}
          >
            {organizationId}
            <Tooltip title={copied ? 'Copied' : 'Copy'}>
              <IconButton
                size="small"
                onClick={handleCopyId}
                aria-label="Copy organization ID"
                sx={{ ml: 0.5 }}
              >
                {copied ? (
                  <CheckIcon fontSize="inherit" />
                ) : (
                  <ContentCopyIcon fontSize="inherit" />
                )}
              </IconButton>
            </Tooltip>
          </Box>
        </ViewField>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Organization Name"
          value={draft.name}
          onChange={handleChange('name')}
          required={isEditing}
          helperText="The internal name for your organization"
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Display Name"
          value={draft.display_name}
          onChange={handleChange('display_name')}
          helperText="Friendly name shown to users (optional)"
        />
      </Grid>

      <Grid size={12}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Description"
          value={draft.description}
          onChange={handleChange('description')}
          multiline
          rows={3}
          helperText="A brief description of your organization"
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Website"
          value={draft.website}
          onChange={handleChange('website')}
          onBlur={handleBlur('website')}
          placeholder={isEditing ? 'https://example.com' : undefined}
          error={isEditing && !!fieldErrors.website}
          helperText={
            isEditing
              ? fieldErrors.website || "Your organization's website"
              : "Your organization's website"
          }
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Logo URL"
          value={draft.logo_url}
          onChange={handleChange('logo_url')}
          onBlur={handleBlur('logo_url')}
          placeholder={isEditing ? 'https://example.com/logo.png' : undefined}
          error={isEditing && !!fieldErrors.logo_url}
          helperText={
            isEditing
              ? fieldErrors.logo_url || "URL to your organization's logo"
              : "URL to your organization's logo"
          }
        />
      </Grid>
    </Grid>
  );
}
