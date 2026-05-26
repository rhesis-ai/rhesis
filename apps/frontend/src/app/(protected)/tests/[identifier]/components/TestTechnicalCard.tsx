'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import { TextField, Typography } from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { isMultiTurnTest } from '@/constants/test-types';
import {
  MultiTurnTestConfig,
  isMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';
import MultiTurnConfigFields, {
  MultiTurnDraft,
  createMultiTurnDraft,
} from './MultiTurnConfigFields';
import FilePreview from '@/components/common/FilePreview';
import { useRouter } from 'next/navigation';

const MONO_SX = {
  fontFamily: '"Sometype Mono", monospace',
  fontSize: '16px',
  lineHeight: '24px',
  fontWeight: 400,
};

interface PromptDraft {
  content: string;
  expected_response: string;
}

interface TestTechnicalCardProps {
  sessionToken: string;
  test: TestDetail;
  onUpdate?: () => void;
}

export default function TestTechnicalCard({
  sessionToken,
  test,
  onUpdate,
}: TestTechnicalCardProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const isMultiTurn = isMultiTurnTest(test.test_type?.type_value);

  const testSources: Array<Record<string, string>> = Array.isArray(
    test.test_metadata?.sources
  )
    ? test.test_metadata.sources
    : [];

  const initialDraft: PromptDraft = {
    content: test.prompt?.content ?? '',
    expected_response: test.prompt?.expected_response ?? '',
  };

  const handleSave = async (draft: PromptDraft) => {
    if (!test.prompt_id) return;
    const apiFactory = new ApiClientFactory(sessionToken);
    const promptsClient = apiFactory.getPromptsClient();
    await promptsClient.updatePrompt(test.prompt_id, {
      content: draft.content,
      expected_response: draft.expected_response,
    });
    notifications.show('Prompts updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
    onUpdate?.();
    router.refresh();
  };

  if (isMultiTurn) {
    const initialConfig: MultiTurnTestConfig | null = isMultiTurnConfig(
      test.test_configuration
    )
      ? (test.test_configuration as MultiTurnTestConfig)
      : null;
    const initialMultiTurnDraft: MultiTurnDraft =
      createMultiTurnDraft(initialConfig);

    const handleMultiTurnSave = async (draft: MultiTurnDraft) => {
      if (!draft.goal || draft.goal.trim().length === 0) {
        notifications.show('Goal cannot be empty', {
          severity: 'error',
          autoHideDuration: 4000,
        });
        throw new Error('Goal cannot be empty');
      }

      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();

      const payload: MultiTurnTestConfig = {
        goal: draft.goal.trim(),
        instructions: draft.instructions?.trim() || undefined,
        restrictions: draft.restrictions?.trim() || undefined,
        scenario: draft.scenario?.trim() || undefined,
        max_turns: draft.max_turns ?? 10,
        min_turns: draft.min_turns,
      };

      await testsClient.updateTest(test.id, {
        test_configuration: payload as unknown as Record<string, unknown>,
      });

      notifications.show('Multi-turn configuration updated', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      onUpdate?.();
      router.refresh();
    };

    return (
      <EditableSection
        title="Prompts"
        initialValue={initialMultiTurnDraft}
        onSave={handleMultiTurnSave}
      >
        {({ draft, setDraft, isEditing }) => (
          <MultiTurnConfigFields
            draft={draft}
            setDraft={setDraft}
            isEditing={isEditing}
          />
        )}
      </EditableSection>
    );
  }

  return (
    <EditableSection
      title="Prompts"
      initialValue={initialDraft}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <Grid container rowSpacing={isEditing ? 2 : '50px'}>
          <Grid size={12}>
            {isEditing ? (
              <TextField
                fullWidth
                label="Test Prompt"
                value={draft.content}
                onChange={e =>
                  setDraft(d => ({ ...d, content: e.target.value }))
                }
                multiline
                rows={8}
                variant="outlined"
                helperText="Infotext"
                inputProps={{ style: MONO_SX }}
                InputProps={{ style: MONO_SX }}
              />
            ) : (
              <ViewField
                label="Test Prompt"
                value={draft.content}
                helperText="Infotext"
                multiline
                inputSx={MONO_SX}
              />
            )}
          </Grid>

          <Grid size={12}>
            {isEditing ? (
              <TextField
                fullWidth
                label="Expected Response"
                value={draft.expected_response}
                onChange={e =>
                  setDraft(d => ({ ...d, expected_response: e.target.value }))
                }
                multiline
                rows={8}
                variant="outlined"
                helperText="Infotext"
                inputProps={{ style: MONO_SX }}
                InputProps={{ style: MONO_SX }}
              />
            ) : (
              <ViewField
                label="Expected Response"
                value={draft.expected_response}
                helperText="Infotext"
                multiline
                inputSx={MONO_SX}
              />
            )}
          </Grid>

          {/* Sources Section (read-only, always visible) */}
          {testSources.length > 0 && (
            <Grid size={12}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Sources
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontStyle: 'italic', mb: 1 }}
              >
                The content shown below is the portion of the source used to
                generate this test case.
              </Typography>
              <Grid container spacing={2}>
                {testSources.map((source, index: number) => {
                  const sourceKey =
                    source.name ||
                    source.document ||
                    source.source ||
                    `source-${index}`;
                  return (
                    <Grid size={12} key={sourceKey}>
                      <FilePreview
                        title={
                          source.name ||
                          source.document ||
                          source.source ||
                          'Unknown Source'
                        }
                        content={source.content || 'No content available'}
                        showCopyButton={true}
                        defaultExpanded={false}
                      />
                    </Grid>
                  );
                })}
              </Grid>
            </Grid>
          )}
        </Grid>
      )}
    </EditableSection>
  );
}
