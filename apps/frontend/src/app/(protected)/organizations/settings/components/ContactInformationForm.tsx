'use client';

import React, { useMemo } from 'react';
import { Grid, TextField } from '@mui/material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateEmail, validatePhone } from '@/utils/validation';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

interface ContactInformationFormProps {
  organization: Organization;
  onUpdate: () => void;
}

interface ContactDraft {
  email: string;
  phone: string;
  address: string;
}

function draftFromOrganization(org: Organization): ContactDraft {
  return {
    email: org.email || '',
    phone: org.phone || '',
    address: org.address || '',
  };
}

export default function ContactInformationForm({
  organization,
  onUpdate,
}: ContactInformationFormProps) {
  const notifications = useNotifications();
  const canUpdateOrg = useCan(Capability.Organization.UPDATE);
  const initialValue = useMemo(
    () => draftFromOrganization(organization),
    [organization]
  );

  const handleSave = async (draft: ContactDraft) => {
    const errors: Record<string, string> = {};

    if (draft.email) {
      const emailValidation = validateEmail(draft.email);
      if (!emailValidation.isValid) {
        errors.email = emailValidation.message || '';
      }
    }

    if (draft.phone) {
      const phoneValidation = validatePhone(draft.phone);
      if (!phoneValidation.isValid) {
        errors.phone = phoneValidation.message || '';
      }
    }

    if (Object.keys(errors).length > 0) {
      notifications.show(Object.values(errors)[0], { severity: 'error' });
      throw new Error('validation');
    }

    try {
      const apiFactory = new ApiClientFactory();
      const organizationsClient = apiFactory.getOrganizationsClient();

      await organizationsClient.updateOrganization(organization.id, {
        email: draft.email || undefined,
        phone: draft.phone || undefined,
        address: draft.address || undefined,
      });

      notifications.show('Contact information updated successfully', {
        severity: 'success',
      });
      onUpdate();
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'validation') {
        throw err;
      }
      notifications.show(
        err instanceof Error
          ? err.message
          : 'Failed to update contact information',
        { severity: 'error' }
      );
      throw err;
    }
  };

  return (
    <EditableSection
      editable={canUpdateOrg}
      title="Contact Information"
      initialValue={initialValue}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <ContactFields
          draft={draft}
          setDraft={setDraft}
          isEditing={isEditing}
        />
      )}
    </EditableSection>
  );
}

function ContactFields({
  draft,
  setDraft,
  isEditing,
}: {
  draft: ContactDraft;
  setDraft: (next: ContactDraft | ((p: ContactDraft) => ContactDraft)) => void;
  isEditing: boolean;
}) {
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>(
    {}
  );

  const handleChange =
    (field: keyof ContactDraft) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setDraft(prev => ({ ...prev, [field]: e.target.value }));
      if (fieldErrors[field]) {
        setFieldErrors(prev => ({ ...prev, [field]: '' }));
      }
    };

  const handleBlur = (field: 'email' | 'phone') => () => {
    const value = draft[field];
    if (value) {
      const validation =
        field === 'email' ? validateEmail(value) : validatePhone(value);
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
            label="Email"
            value={draft.email}
            onChange={handleChange('email')}
            onBlur={handleBlur('email')}
            placeholder="contact@example.com"
            error={!!fieldErrors.email}
            helperText={
              fieldErrors.email || 'Primary contact email for your organization'
            }
          />
        ) : (
          <ViewField
            label="Email"
            value={draft.email}
            helperText="Primary contact email for your organization"
          />
        )}
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Phone"
            value={draft.phone}
            onChange={handleChange('phone')}
            onBlur={handleBlur('phone')}
            placeholder="+1 (555) 123-4567"
            error={!!fieldErrors.phone}
            helperText={fieldErrors.phone || 'Primary contact phone number'}
          />
        ) : (
          <ViewField
            label="Phone"
            value={draft.phone}
            helperText="Primary contact phone number"
          />
        )}
      </Grid>

      <Grid size={12}>
        {isEditing ? (
          <TextField
            fullWidth
            label="Address"
            value={draft.address}
            onChange={handleChange('address')}
            multiline
            rows={3}
            placeholder="123 Main St, City, State, ZIP"
            helperText="Physical address of your organization"
          />
        ) : (
          <ViewField
            label="Address"
            value={draft.address}
            helperText="Physical address of your organization"
            multiline
          />
        )}
      </Grid>
    </Grid>
  );
}
