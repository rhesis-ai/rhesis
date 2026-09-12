'use client';

import * as React from 'react';
import { Box, Button, Typography, useTheme } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import DeleteIcon from '@mui/icons-material/Delete';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import JsonMonacoField from '@/app/(protected)/endpoints/[identifier]/components/JsonMonacoField';

interface TestParametersBlockProps {
  test: TestDetail;
  onUpdate?: () => void;
}

export default function TestParametersBlock({
  test,
  onUpdate,
}: TestParametersBlockProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const canEdit = useCan(Capability.Test.UPDATE);
  const monacoTheme =
    theme.palette.mode === 'dark' ? 'vs-dark' : 'vs';

  const currentParams = test.test_parameters ?? null;
  const hasParams =
    currentParams !== null && Object.keys(currentParams).length > 0;

  const [isEditing, setIsEditing] = React.useState(false);
  const [draft, setDraft] = React.useState('');
  const [isSaving, setIsSaving] = React.useState(false);

  const startEditing = React.useCallback(() => {
    setDraft(
      hasParams ? JSON.stringify(currentParams, null, 2) : '{\n  \n}'
    );
    setIsEditing(true);
  }, [hasParams, currentParams]);

  const cancelEditing = React.useCallback(() => {
    setIsEditing(false);
    setDraft('');
  }, []);

  const handleSave = React.useCallback(async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(draft);
    } catch {
      notifications.show('Invalid JSON', {
        severity: 'error',
        autoHideDuration: 4000,
      });
      return;
    }

    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      notifications.show('Test parameters must be a JSON object', {
        severity: 'error',
        autoHideDuration: 4000,
      });
      return;
    }

    setIsSaving(true);
    try {
      const apiFactory = new ApiClientFactory();
      const testsClient = apiFactory.getTestsClient();
      await testsClient.updateTest(test.id, {
        test_parameters: parsed,
      });
      notifications.show('Test parameters updated', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      setIsEditing(false);
      onUpdate?.();
    } catch {
      notifications.show('Failed to save test parameters', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsSaving(false);
    }
  }, [draft, test.id, notifications, onUpdate]);

  const handleClear = React.useCallback(async () => {
    setIsSaving(true);
    try {
      const apiFactory = new ApiClientFactory();
      const testsClient = apiFactory.getTestsClient();
      await testsClient.updateTest(test.id, {
        test_parameters: null as unknown as Record<string, unknown>,
      });
      notifications.show('Test parameters cleared', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      setIsEditing(false);
      onUpdate?.();
    } catch {
      notifications.show('Failed to clear test parameters', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsSaving(false);
    }
  }, [test.id, notifications, onUpdate]);

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: '2px',
        }}
      >
        <Box>
          <Typography
            sx={{
              fontSize: 18,
              fontWeight: 700,
              lineHeight: '25px',
              color: 'text.primary',
            }}
          >
            Test Parameters
          </Typography>
          <Typography
            sx={{
              fontSize: 12,
              lineHeight: '18px',
              color: 'text.secondary',
              display: 'block',
              mb: 2,
            }}
          >
            Per-test key-value data available in endpoint mappings as{' '}
            {'{{ test_parameters.<key> }}'}
          </Typography>
        </Box>
        {canEdit && !isEditing && (
          <Button
            size="small"
            startIcon={<EditIcon />}
            onClick={startEditing}
          >
            Edit
          </Button>
        )}
      </Box>

      {isEditing ? (
        <Box>
          <JsonMonacoField
            editorKey={`test-parameters-${test.id}`}
            height="200px"
            theme={monacoTheme}
            value={draft}
            onChange={setDraft}
          />
          <Box
            sx={{ display: 'flex', gap: 1, mt: 1, justifyContent: 'flex-end' }}
          >
            {hasParams && (
              <Button
                size="small"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleClear}
                disabled={isSaving}
              >
                Clear
              </Button>
            )}
            <Button
              size="small"
              startIcon={<CancelIcon />}
              onClick={cancelEditing}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              size="small"
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={isSaving}
            >
              Save
            </Button>
          </Box>
        </Box>
      ) : hasParams ? (
        <Box
          sx={{
            p: 2,
            borderRadius: 1,
            backgroundColor: 'action.hover',
            fontFamily: '"Sometype Mono", monospace',
            fontSize: theme.typography.body2.fontSize,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {JSON.stringify(currentParams, null, 2)}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No parameters defined
        </Typography>
      )}
    </Box>
  );
}
