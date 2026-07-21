'use client';

import React, { useMemo } from 'react';
import { Grid, TextField } from '@mui/material';
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateUrl, normalizeUrl } from '@/utils/validation';
import EditableSection from '@/components/common/EditableSection';
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
          draft={draft}
          setDraft={setDraft}
          isEditing={isEditing}
        />
      )}
    </EditableSection>
  );
}

function DetailsFields({
  draft,
  setDraft,
  isEditing,
}: {
  draft: DetailsDraft;
  setDraft: (next: DetailsDraft | ((p: DetailsDraft) => DetailsDraft)) => void;
  isEditing: boolean;
}) {
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>(
    {}
  );

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

  const gridSpacing = isEditing ? 2 : '50px';
  const columnSpacing = isEditing ? 2 : '30px';

  return (
    <Grid container columnSpacing={columnSpacing} rowSpacing={gridSpacing}>
      <Grid size={{ xs: 12, md: 6 }}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Organization Name"
            value={draft.name}
            onChange={handleChange('name')}
            required
            helperText="The internal name for your organization"
          />
        ) : (
          <ViewField
            label="Organization Name"
            value={draft.name}
            helperText="The internal name for your organization"
          />
        )}
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Display Name"
            value={draft.display_name}
            onChange={handleChange('display_name')}
            helperText="Friendly name shown to users (optional)"
          />
        ) : (
          <ViewField
            label="Display Name"
            value={draft.display_name}
            helperText="Friendly name shown to users (optional)"
          />
        )}
      </Grid>

      <Grid size={12}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Description"
            value={draft.description}
            onChange={handleChange('description')}
            multiline
            rows={3}
            helperText="A brief description of your organization"
          />
        ) : (
          <ViewField
            label="Description"
            value={draft.description}
            helperText="A brief description of your organization"
            multiline
          />
        )}
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Website"
            value={draft.website}
            onChange={handleChange('website')}
            onBlur={handleBlur('website')}
            placeholder="https://example.com"
            error={!!fieldErrors.website}
            helperText={fieldErrors.website || "Your organization's website"}
          />
        ) : (
          <ViewField
            label="Website"
            value={draft.website}
            helperText="Your organization's website"
          />
        )}
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Logo URL"
            value={draft.logo_url}
            onChange={handleChange('logo_url')}
            onBlur={handleBlur('logo_url')}
            placeholder="https://example.com/logo.png"
            error={!!fieldErrors.logo_url}
            helperText={
              fieldErrors.logo_url || "URL to your organization's logo"
            }
          />
        ) : (
          <ViewField
            label="Logo URL"
            value={draft.logo_url}
            helperText="URL to your organization's logo"
          />
        )}
      </Grid>
    </Grid>
  );
}
