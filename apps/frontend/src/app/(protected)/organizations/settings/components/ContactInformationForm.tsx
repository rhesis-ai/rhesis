'use client';

import React, { useMemo } from 'react';
import { Grid } from '@mui/material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateEmail, validatePhone } from '@/utils/validation';
import { SECTION_GRID } from '@/styles/theme-constants';
import EditableSection from '@/components/common/EditableSection';
import EditableField from '@/components/common/EditableField';
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
          label="Email"
          value={draft.email}
          onChange={handleChange('email')}
          onBlur={handleBlur('email')}
          placeholder={isEditing ? 'contact@example.com' : undefined}
          error={isEditing && !!fieldErrors.email}
          helperText={
            isEditing
              ? fieldErrors.email ||
                'Primary contact email for your organization'
              : 'Primary contact email for your organization'
          }
        />
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Phone"
          value={draft.phone}
          onChange={handleChange('phone')}
          onBlur={handleBlur('phone')}
          placeholder={isEditing ? '+1 (555) 123-4567' : undefined}
          error={isEditing && !!fieldErrors.phone}
          helperText={
            isEditing
              ? fieldErrors.phone || 'Primary contact phone number'
              : 'Primary contact phone number'
          }
        />
      </Grid>

      <Grid size={12}>
        <EditableField
          fullWidth
          editing={isEditing}
          label="Address"
          value={draft.address}
          onChange={handleChange('address')}
          multiline
          rows={3}
          placeholder={isEditing ? '123 Main St, City, State, ZIP' : undefined}
          helperText="Physical address of your organization"
        />
      </Grid>
    </Grid>
  );
}
