'use client';

import { useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import EditableSection from '@/components/common/EditableSection';
import { useNotifications } from '@/components/common/NotificationContext';
import { asVersionInfo, validateVersionInfoDraft } from '@/utils/version-info';
import { JsonPreview } from '../../components/JsonPreview';
import { testPreviewSx } from '../../components/endpoint-styles';
import JsonMonacoField from './JsonMonacoField';
import { useEndpointDetailContext } from './EndpointDetailContext';

interface VersionInfoDraft {
  body: string;
}

const EMPTY_DRAFT = '{\n  \n}';

export default function EndpointVersionInfoSection() {
  const { endpoint, saveFields, editorTheme } = useEndpointDetailContext();
  const canEditEndpoint = useCan(Capability.Endpoint.UPDATE);
  const notifications = useNotifications();

  const current = asVersionInfo(endpoint.version_info);
  const initialValue = useMemo<VersionInfoDraft>(
    () => ({
      body: current ? JSON.stringify(current, null, 2) : EMPTY_DRAFT,
    }),
    // Re-seed only when the stored value changes, not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [endpoint.version_info]
  );

  const handleSave = async (draft: VersionInfoDraft): Promise<boolean> => {
    const error = validateVersionInfoDraft(draft.body);
    if (error) {
      notifications.show(error, { severity: 'error' });
      // Keeps the section in edit mode so the bad value is still there to fix.
      return false;
    }

    const trimmed = draft.body.trim();
    const parsed =
      trimmed === '' ? {} : (JSON.parse(trimmed) as Record<string, unknown>);

    // An emptied editor clears the column rather than storing a meaningless {}.
    await saveFields({
      version_info: Object.keys(parsed).length > 0 ? parsed : null,
    });
    return true;
  };

  return (
    <EditableSection
      editable={canEditEndpoint}
      title="Version Information"
      subtitle="Free-form JSON describing the system behind this endpoint — prompt version, model, parameters. Recorded on every test run, so past runs keep showing the version that produced them. An endpoint that returns its own version through the version_info response mapping overrides this per run. Avoid secrets: this is shown wherever the endpoint is visible."
      initialValue={initialValue}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) =>
        isEditing ? (
          <JsonMonacoField
            editorKey={`endpoint-version-info-${endpoint.id}`}
            height="200px"
            theme={editorTheme}
            value={draft.body}
            onChange={body => setDraft(() => ({ body }))}
          />
        ) : current ? (
          <Box component="pre" sx={testPreviewSx}>
            <JsonPreview value={current} />
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No version information configured
          </Typography>
        )
      }
    </EditableSection>
  );
}
