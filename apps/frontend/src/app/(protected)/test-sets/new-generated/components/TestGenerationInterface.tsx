'use client';

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardContent,
  Typography,
  TextField,
  IconButton,
  Button,
  Chip,
  Paper,
  CircularProgress,
  Tooltip,
  Skeleton,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SendIcon from '@mui/icons-material/Send';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DescriptionIcon from '@mui/icons-material/Description';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import EndpointsIcon from '@/components/EndpointsIcon';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import FolderIcon from '@mui/icons-material/Folder';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import type { Theme } from '@mui/material/styles';
import {
  ConfigChips,
  AnyTestSample,
  MultiTurnTestSample,
  ChatMessage,
  TestType,
} from './shared/types';
import { SourceData } from '@/utils/api-client/interfaces/test-set';
import { ConversationTurn } from '@/utils/api-client/interfaces/test-results';
import ChipGroup from './shared/ChipGroup';
import TestSampleCard from './shared/TestSampleCard';
import ActionBar from '@/components/common/ActionBar';
import BaseDrawer from '@/components/common/BaseDrawer';
import EndpointSelector from './shared/EndpointSelector';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  useEndpoint,
  useProject,
  useInvokeEndpoint,
} from '@/hooks/useEndpoints';
import { TEST_TYPES } from '@/constants/test-types';

function extractResponseText(response: unknown): string {
  if (typeof response === 'string') return response;
  const r = response as Record<string, unknown> | null;
  if (r?.output != null) return String(r.output);
  if (r?.text != null) return String(r.text);
  if (r?.response != null) return String(r.response);
  if (r?.content != null) return String(r.content);
  return JSON.stringify(response);
}

interface TestGenerationInterfaceProps {
  testType: TestType;
  configChips: ConfigChips;
  testSamples: AnyTestSample[];
  chatMessages: ChatMessage[];
  description: string;
  selectedSources: SourceData[];
  selectedEndpointId: string | null;
  onChipToggle: (category: keyof ConfigChips, chipId: string) => void;
  onSendMessage: (message: string) => void;
  onRateSample: (sampleId: string, rating: number) => void;
  onSampleFeedbackChange: (sampleId: string, feedback: string) => void;
  onLoadMoreSamples: () => void;
  onRegenerateSamples: () => void;
  onRegenerate: (sampleId: string, feedback: string) => void;
  onBack: () => void;
  onNext: () => void;
  onEndpointChange: (endpointId: string | null) => void;
  onSourceRemove: (sourceId: string) => void;
  isGenerating: boolean;
  isLoadingConfig: boolean;
  isLoadingSamples: boolean;
  isLoadingMore: boolean;
  regeneratingSampleId: string | null;
  onSamplesUpdate?: (samples: AnyTestSample[]) => void;
}

/**
 * TestGenerationInterface Component
 * 2-panel interface with configuration on left and preview on right
 */
export default function TestGenerationInterface({
  testType,
  configChips,
  testSamples,
  chatMessages: _chatMessages,
  description: _description,
  selectedSources,
  selectedEndpointId,
  onChipToggle,
  onSendMessage,
  onRateSample,
  onSampleFeedbackChange,
  onLoadMoreSamples,
  onRegenerateSamples,
  onRegenerate,
  onBack,
  onNext,
  onEndpointChange,
  onSourceRemove,
  isGenerating,
  isLoadingConfig,
  isLoadingSamples,
  isLoadingMore,
  regeneratingSampleId,
  onSamplesUpdate,
}: TestGenerationInterfaceProps) {
  const [inputMessage, setInputMessage] = useState('');
  const [localTestSamples, setLocalTestSamples] =
    useState<AnyTestSample[]>(testSamples);
  const [isFetchingResponses, setIsFetchingResponses] = useState(false);
  const [processedSampleIds, setProcessedSampleIds] = useState<Set<string>>(
    new Set()
  );
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [showEndpointModal, setShowEndpointModal] = useState(false);
  const { data: session } = useSession();
  const invokeEndpointMutation = useInvokeEndpoint(
    session?.session_token ?? ''
  );
  const { data: selectedEndpoint } = useEndpoint(
    session?.session_token ?? '',
    selectedEndpointId ?? '',
    !!selectedEndpointId
  );
  const { data: selectedEndpointProject } = useProject(
    session?.session_token ?? '',
    selectedEndpoint?.project_id ?? '',
    !!selectedEndpoint?.project_id
  );

  // Sync local samples with prop changes - merge new samples while preserving existing responses
  useEffect(() => {
    if (testSamples.length === 0) {
      setLocalTestSamples([]);
      setProcessedSampleIds(new Set());
      return;
    }

    // Check if sample IDs have changed (samples were regenerated)
    const existingSampleIds = new Set(localTestSamples.map(s => s.id));
    const sampleIdsChanged =
      testSamples.length !== localTestSamples.length ||
      testSamples.some(s => !existingSampleIds.has(s.id));

    if (sampleIdsChanged) {
      setProcessedSampleIds(new Set());
    }

    // Create a map of existing samples with responses
    const existingSamplesMap = new Map(
      localTestSamples.map(sample => [sample.id, sample])
    );

    // Merge: keep existing samples with responses/conversation, ratings, and feedback
    const mergedSamples = testSamples.map(newSample => {
      const existingSample = existingSamplesMap.get(newSample.id);

      // If sample exists, merge it to preserve local state
      if (existingSample) {
        // Merge: use new sample as base but preserve response/conversation data and user interactions
        const merged = {
          ...newSample,
          // Preserve rating and feedback from both sources (prefer existing if set)
          rating: existingSample.rating ?? newSample.rating,
          feedback: existingSample.feedback || newSample.feedback,
        };

        // Preserve response data for single-turn
        if (existingSample.response) {
          merged.response = existingSample.response;
        }
        if (existingSample.isLoadingResponse) {
          merged.isLoadingResponse = existingSample.isLoadingResponse;
        }
        if (existingSample.responseError) {
          merged.responseError = existingSample.responseError;
        }

        // Preserve conversation data for multi-turn
        if (
          existingSample.testType === 'multi_turn' &&
          newSample.testType === 'multi_turn'
        ) {
          const mergedMultiTurn = merged as MultiTurnTestSample;
          if (existingSample.conversation) {
            mergedMultiTurn.conversation = existingSample.conversation;
          }
          if (existingSample.isLoadingConversation) {
            mergedMultiTurn.isLoadingConversation =
              existingSample.isLoadingConversation;
          }
          if (existingSample.conversationError) {
            mergedMultiTurn.conversationError =
              existingSample.conversationError;
          }
        }

        return merged;
      }

      // Otherwise use the new sample from props
      return newSample;
    });

    setLocalTestSamples(mergedSamples);
    // localTestSamples intentionally excluded - adding would cause infinite loop (effect sets it)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testSamples]);

  // Notify parent whenever local samples change
  useEffect(() => {
    if (onSamplesUpdate) onSamplesUpdate(localTestSamples);
    // onSamplesUpdate intentionally excluded to avoid re-triggering on callback identity change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localTestSamples]);

  const endpointInfo = useMemo(() => {
    if (!selectedEndpoint) return null;
    return {
      name: selectedEndpoint.name,
      projectName: selectedEndpointProject?.name ?? 'Unknown Project',
      environment: selectedEndpoint.environment,
      projectIcon: selectedEndpointProject?.icon,
    };
  }, [selectedEndpoint, selectedEndpointProject]);

  // Reset processed IDs and clear responses when the endpoint changes
  useEffect(() => {
    setProcessedSampleIds(new Set());
    setLocalTestSamples(prev =>
      prev.map(sample => {
        const newSample = { ...sample };
        delete newSample.response;
        delete newSample.responseError;
        delete newSample.isLoadingResponse;
        return newSample;
      })
    );
  }, [selectedEndpointId]);

  // Fetch responses from endpoint for all unprocessed samples (in parallel).
  // Only triggered explicitly via fetchTrigger (e.g. "Generate Responses" button).
  useEffect(() => {
    if (fetchTrigger === 0) return;

    const fetchResponses = async () => {
      if (
        !selectedEndpointId ||
        !session?.session_token ||
        localTestSamples.length === 0 ||
        isFetchingResponses
      ) {
        return;
      }

      const samplesToFetch = localTestSamples.filter(
        sample =>
          !processedSampleIds.has(sample.id) &&
          !sample.response &&
          !sample.isLoadingResponse
      );

      if (samplesToFetch.length === 0) {
        return;
      }

      setIsFetchingResponses(true);

      const apiFactory = new ApiClientFactory(session.session_token);
      const testsClient = apiFactory.getTestsClient();

      // Mark all samples as loading
      setLocalTestSamples(prev =>
        prev.map(sample => {
          if (!samplesToFetch.some(s => s.id === sample.id)) return sample;
          if (sample.testType === 'single_turn') {
            const s = { ...sample, isLoadingResponse: true };
            delete s.response;
            delete s.responseError;
            return s;
          }
          const s = { ...sample, isLoadingConversation: true };
          delete s.response;
          delete s.responseError;
          delete s.conversation;
          delete s.conversationError;
          return s;
        })
      );

      // Fire all requests in parallel, updating each card as it resolves
      const promises = samplesToFetch.map(async sample => {
        try {
          if (sample.testType === 'single_turn') {
            const response = await invokeEndpointMutation.mutateAsync({
              id: selectedEndpointId,
              inputData: { input: sample.prompt },
            });

            const responseText = extractResponseText(response);

            setLocalTestSamples(prev =>
              prev.map(s =>
                s.id === sample.id
                  ? {
                      ...s,
                      response: responseText,
                      isLoadingResponse: false,
                      responseError: undefined,
                    }
                  : s
              )
            );
          } else {
            const executeResponse = await testsClient.executeTest({
              endpoint_id:
                selectedEndpointId as `${string}-${string}-${string}-${string}-${string}`,
              test_configuration: {
                goal: sample.prompt.goal,
                instructions: sample.prompt.instructions,
                restrictions: sample.prompt.restrictions,
                scenario: sample.prompt.scenario,
              },
              behavior: sample.behavior,
              topic: sample.topic,
              category: sample.category,
              evaluate_metrics: false,
            });

            let conversation: ConversationTurn[] = [];
            if (
              executeResponse.test_output &&
              typeof executeResponse.test_output === 'object'
            ) {
              conversation = Array.isArray(
                executeResponse.test_output.conversation_summary
              )
                ? executeResponse.test_output.conversation_summary
                : [];
            }

            setLocalTestSamples(prev =>
              prev.map(s =>
                s.id === sample.id
                  ? {
                      ...s,
                      conversation,
                      isLoadingConversation: false,
                      response: `Goal: ${sample.prompt.goal} (${conversation.length} turns)`,
                      conversationError: undefined,
                    }
                  : s
              )
            );
          }

          return { id: sample.id, success: true };
        } catch (error) {
          const errorMsg =
            error instanceof Error ? error.message : 'Failed to fetch response';

          setLocalTestSamples(prev =>
            prev.map(s => {
              if (s.id !== sample.id) return s;
              if (s.testType === 'single_turn') {
                return {
                  ...s,
                  isLoadingResponse: false,
                  responseError: errorMsg,
                  response: undefined,
                };
              }
              return {
                ...s,
                isLoadingConversation: false,
                conversationError: errorMsg,
                conversation: undefined,
              };
            })
          );

          return { id: sample.id, success: false };
        }
      });

      const results = await Promise.allSettled(promises);

      const newProcessedIds = new Set(processedSampleIds);
      for (const result of results) {
        if (result.status === 'fulfilled') {
          newProcessedIds.add(result.value.id);
        }
      }
      setProcessedSampleIds(newProcessedIds);

      setIsFetchingResponses(false);
    };

    fetchResponses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchTrigger]);

  const handleSendMessage = useCallback(() => {
    if (inputMessage.trim()) {
      onSendMessage(inputMessage);
      setInputMessage('');
    }
  }, [inputMessage, onSendMessage]);

  const handleKeyPress = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage]
  );

  // Wrapper for onRateSample that also updates local state
  const handleRateSample = useCallback(
    (sampleId: string, rating: number) => {
      // Update local state
      setLocalTestSamples(prev =>
        prev.map(sample =>
          sample.id === sampleId ? { ...sample, rating } : sample
        )
      );
      // Call parent callback
      onRateSample(sampleId, rating);
    },
    [onRateSample]
  );

  // Wrapper for onSampleFeedbackChange that also updates local state
  const handleSampleFeedbackChange = useCallback(
    (sampleId: string, feedback: string) => {
      // Update local state
      setLocalTestSamples(prev =>
        prev.map(sample =>
          sample.id === sampleId ? { ...sample, feedback } : sample
        )
      );
      // Call parent callback
      onSampleFeedbackChange(sampleId, feedback);
    },
    [onSampleFeedbackChange]
  );

  // Manual fetch for a single sample (for multi-turn "Simulate Response" button)
  const handleFetchSampleResponse = useCallback(
    async (sampleId: string) => {
      if (!selectedEndpointId || !session?.session_token) return;

      const sample = localTestSamples.find(s => s.id === sampleId);
      if (!sample) return;
      if (processedSampleIds.has(sampleId) || sample.isLoadingResponse) return;
      if (sample.testType === 'multi_turn' && sample.isLoadingConversation)
        return;

      const apiFactory = new ApiClientFactory(session.session_token);
      const testsClient = apiFactory.getTestsClient();

      // Mark sample as loading
      setLocalTestSamples(prev =>
        prev.map(s => {
          if (s.id !== sampleId) return s;
          return s.testType === 'single_turn'
            ? {
                ...s,
                isLoadingResponse: true,
                response: undefined,
                responseError: undefined,
              }
            : {
                ...s,
                isLoadingConversation: true,
                response: undefined,
                responseError: undefined,
                conversation: undefined,
                conversationError: undefined,
              };
        })
      );

      try {
        if (sample.testType === 'single_turn') {
          const response = await invokeEndpointMutation.mutateAsync({
            id: selectedEndpointId,
            inputData: { input: sample.prompt },
          });
          const responseText = extractResponseText(response);

          setLocalTestSamples(prev =>
            prev.map(s =>
              s.id === sampleId
                ? {
                    ...s,
                    response: responseText,
                    isLoadingResponse: false,
                    responseError: undefined,
                  }
                : s
            )
          );
        } else {
          const executeResponse = await testsClient.executeTest({
            endpoint_id:
              selectedEndpointId as `${string}-${string}-${string}-${string}-${string}`,
            test_configuration: {
              goal: sample.prompt.goal,
              instructions: sample.prompt.instructions,
              restrictions: sample.prompt.restrictions,
              scenario: sample.prompt.scenario,
            },
            behavior: sample.behavior,
            topic: sample.topic,
            category: sample.category,
            evaluate_metrics: false,
          });

          let conversation: ConversationTurn[] = [];
          if (
            executeResponse.test_output &&
            typeof executeResponse.test_output === 'object'
          ) {
            conversation = Array.isArray(
              executeResponse.test_output.conversation_summary
            )
              ? executeResponse.test_output.conversation_summary
              : [];
          }

          setLocalTestSamples(prev =>
            prev.map(s =>
              s.id === sampleId
                ? {
                    ...s,
                    conversation,
                    isLoadingConversation: false,
                    response: `Goal: ${sample.prompt.goal} (${conversation.length} turns)`,
                    conversationError: undefined,
                  }
                : s
            )
          );
        }

        setProcessedSampleIds(prev => new Set(prev).add(sampleId));
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : 'Failed to fetch response';

        setLocalTestSamples(prev =>
          prev.map(s => {
            if (s.id !== sampleId) return s;
            return s.testType === 'single_turn'
              ? {
                  ...s,
                  isLoadingResponse: false,
                  responseError: errorMsg,
                  response: undefined,
                }
              : {
                  ...s,
                  isLoadingConversation: false,
                  conversationError: errorMsg,
                  conversation: undefined,
                };
          })
        );

        setProcessedSampleIds(prev => new Set(prev).add(sampleId));
      }
    },
    [
      selectedEndpointId,
      session?.session_token,
      localTestSamples,
      processedSampleIds,
      invokeEndpointMutation,
    ]
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      {/* 2 Panel Layout – grows to fill all available space above the ActionBar */}
      <Box sx={{ flex: 1, minHeight: 0, mb: 2 }}>
        <Paper
          elevation={0}
          sx={{
            display: 'flex',
            height: '100%',
            overflow: 'hidden',
            borderRadius: BORDER_RADIUS.md,
            border: (theme: Theme) =>
              `1px solid ${theme.palette.greyscale.border}`,
            boxShadow: (theme: Theme) =>
              theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
            bgcolor: (theme: Theme) =>
              theme.palette.mode === 'light'
                ? '#ffffff'
                : theme.palette.greyscale.surface1,
          }}
        >
          {/* LEFT PANEL - Configuration */}
          <Box
            sx={{
              width: '33%',
              borderRight: 1,
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Card
              elevation={0}
              sx={{
                height: '100%',
                borderRadius: 0, // Intentional: flush with panel edges
                border: 0,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Header */}
              <CardHeader
                sx={{
                  borderBottom: 1,
                  borderColor: 'divider',
                  minHeight: 64,
                  alignItems: 'center',
                }}
                title={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography variant="h6" fontWeight="bold">
                      Test Set Configuration
                    </Typography>
                    <Tooltip
                      title="Configure test parameters to guide AI generation."
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: theme => theme.iconSizes.small,
                          color: 'text.secondary',
                          cursor: 'help',
                        }}
                      />
                    </Tooltip>
                  </Box>
                }
              />

              {/* Scrollable Configuration Area */}
              <Box
                sx={{
                  flex: 1,
                  overflow: 'auto',
                  p: 3,
                  position: 'relative',
                }}
              >
                {/* Behavior Testing */}
                <Box sx={{ mb: 4 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: theme => theme.shape.circular,
                        bgcolor: 'primary.main',
                      }}
                    />
                    <Typography variant="subtitle2" fontWeight="bold">
                      Behaviors
                    </Typography>
                  </Box>
                  <ChipGroup
                    chips={configChips.behavior}
                    onToggle={chipId => onChipToggle('behavior', chipId)}
                  />
                  {isLoadingConfig && configChips.behavior.length === 0 && (
                    <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                      <Skeleton
                        variant="rounded"
                        width="30%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                      <Skeleton
                        variant="rounded"
                        width="22%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                      <Skeleton
                        variant="rounded"
                        width="35%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                    </Box>
                  )}
                </Box>

                {/* Topics */}
                <Box sx={{ mb: 4 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: theme => theme.shape.circular,
                        bgcolor: 'success.main',
                      }}
                    />
                    <Typography variant="subtitle2" fontWeight="bold">
                      Topics
                    </Typography>
                  </Box>
                  <ChipGroup
                    chips={configChips.topics}
                    onToggle={chipId => onChipToggle('topics', chipId)}
                  />
                  {isLoadingConfig && configChips.topics.length === 0 && (
                    <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                      <Skeleton
                        variant="rounded"
                        width="25%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                      <Skeleton
                        variant="rounded"
                        width="20%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                      <Skeleton
                        variant="rounded"
                        width="28%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                    </Box>
                  )}
                </Box>

                {/* Category */}
                <Box sx={{ mb: 4 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 2,
                    }}
                  >
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: theme => theme.shape.circular,
                        bgcolor: 'secondary.main',
                      }}
                    />
                    <Typography variant="subtitle2" fontWeight="bold">
                      Categories
                    </Typography>
                  </Box>
                  <ChipGroup
                    chips={configChips.category}
                    onToggle={chipId => onChipToggle('category', chipId)}
                  />
                  {isLoadingConfig && configChips.category.length === 0 && (
                    <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                      <Skeleton
                        variant="rounded"
                        width="32%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                      <Skeleton
                        variant="rounded"
                        width="22%"
                        height={28}
                        sx={{ borderRadius: theme => theme.shape.borderRadius }}
                      />
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Selected Sources Section */}
              {selectedSources.length > 0 && (
                <Box
                  sx={{
                    p: 2,
                    borderTop: 1,
                    borderColor: 'divider',
                    bgcolor: 'background.paper',
                  }}
                >
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                    sx={{ mb: 1 }}
                  >
                    Selected sources
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {selectedSources.map(source => (
                      <Chip
                        key={source.id}
                        icon={<DescriptionIcon />}
                        label={source.name || source.id}
                        size="small"
                        variant="outlined"
                        onDelete={() => onSourceRemove(source.id)}
                      />
                    ))}
                  </Box>
                </Box>
              )}

              {/* Chat Input */}
              <Box
                sx={{
                  p: 2,
                  borderTop: 1,
                  borderColor: 'divider',
                  bgcolor: 'background.default',
                }}
              >
                <Paper
                  elevation={1}
                  sx={{
                    borderRadius: theme => theme.shape.borderRadius * 0.75,
                    border: 1,
                    borderColor: 'primary.light',
                    display: 'flex',
                    alignItems: 'center',
                    p: 0.5,
                  }}
                >
                  <TextField
                    fullWidth
                    placeholder="Further refine test generation..."
                    value={inputMessage}
                    onChange={e => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    variant="standard"
                    size="small"
                    InputProps={{
                      disableUnderline: true,
                    }}
                    sx={{ mx: 1 }}
                  />
                  <IconButton
                    size="small"
                    onClick={handleSendMessage}
                    disabled={!inputMessage.trim()}
                    sx={{
                      bgcolor: 'primary.main',
                      color: 'primary.contrastText',
                      '&:hover': {
                        bgcolor: 'primary.dark',
                      },
                      '&:disabled': {
                        bgcolor: 'action.disabledBackground',
                      },
                    }}
                  >
                    <SendIcon fontSize="small" />
                  </IconButton>
                </Paper>
              </Box>
            </Card>
          </Box>

          {/* RIGHT PANEL - Preview */}
          <Box
            sx={{
              width: '67%',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Card
              elevation={0}
              sx={{
                height: '100%',
                borderRadius: 0, // Intentional: flush with panel edges
                border: 0,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Header */}
              <CardHeader
                sx={{
                  borderBottom: 1,
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                  minHeight: 64,
                  alignItems: 'center',
                  '& .MuiCardHeader-action': { alignSelf: 'center', m: 0 },
                }}
                title={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h6" fontWeight="bold">
                      Review Samples
                    </Typography>
                    <Chip
                      label={
                        testType === 'single_turn'
                          ? TEST_TYPES.SINGLE_TURN
                          : TEST_TYPES.MULTI_TURN
                      }
                      size="small"
                      color={
                        testType === 'single_turn' ? 'primary' : 'secondary'
                      }
                      sx={{ ml: 1 }}
                    />
                    <Tooltip
                      title="Preview of generated test samples. Rate them to improve future generations."
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: theme => theme.iconSizes.small,
                          color: 'text.secondary',
                          cursor: 'help',
                        }}
                      />
                    </Tooltip>
                  </Box>
                }
                action={
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<RefreshIcon />}
                      onClick={onRegenerateSamples}
                      disabled={isLoadingSamples}
                      sx={{ textTransform: 'none' }}
                    >
                      Regenerate Samples
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={
                        endpointInfo ? <SwapHorizIcon /> : <EndpointsIcon />
                      }
                      endIcon={
                        endpointInfo ? (
                          <CloseIcon
                            fontSize="small"
                            onClick={e => {
                              e.stopPropagation();
                              onEndpointChange(null);
                            }}
                            sx={{
                              ml: 0.5,
                              '&:hover': {
                                color: 'error.main',
                              },
                            }}
                          />
                        ) : undefined
                      }
                      onClick={() => setShowEndpointModal(true)}
                      sx={{ textTransform: 'none' }}
                    >
                      {endpointInfo
                        ? endpointInfo.name
                        : testType === 'multi_turn'
                          ? 'Show Live Responses'
                          : 'Show Live Responses'}
                    </Button>
                  </Box>
                }
              />

              {/* Scrollable Samples Area */}
              <CardContent
                sx={{
                  flex: 1,
                  p: 0,
                  overflow: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {localTestSamples.length === 0 &&
                !isLoadingSamples &&
                !isGenerating ? (
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      textAlign: 'center',
                      flex: 1,
                    }}
                  >
                    <VisibilityIcon
                      sx={{
                        fontSize: theme => theme.iconSizes.xlarge,
                        opacity: 0.3,
                        mb: 2,
                      }}
                    />
                    <Typography
                      variant="h6"
                      color="text.secondary"
                      gutterBottom
                    >
                      No samples generated yet
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Adjust the configuration to generate test samples
                    </Typography>
                  </Box>
                ) : (
                  <Box sx={{ p: 3 }}>
                    {localTestSamples.map(sample => (
                      <TestSampleCard
                        key={sample.id}
                        sample={sample}
                        onRate={handleRateSample}
                        onFeedbackChange={handleSampleFeedbackChange}
                        onRegenerate={onRegenerate}
                        isRegenerating={regeneratingSampleId === sample.id}
                        endpointName={endpointInfo?.name}
                        projectName={endpointInfo?.projectName}
                        projectIcon={endpointInfo?.projectIcon}
                        actionButton={
                          testType === 'multi_turn' &&
                          sample.testType === 'multi_turn' &&
                          selectedEndpointId ? (
                            <Button
                              variant="contained"
                              size="small"
                              startIcon={<FolderIcon />}
                              onClick={() =>
                                handleFetchSampleResponse(sample.id)
                              }
                              sx={{ textTransform: 'none' }}
                            >
                              Simulate Response
                            </Button>
                          ) : undefined
                        }
                      />
                    ))}

                    {(isLoadingConfig || isLoadingSamples || isGenerating) && (
                      <Box>
                        {(localTestSamples.length === 0
                          ? ['initial-1', 'initial-2', 'initial-3']
                          : ['loading']
                        ).map(skeletonKey => (
                          <Card
                            key={`skeleton-${skeletonKey}`}
                            elevation={0}
                            sx={{
                              mb: 2,
                              borderRadius: BORDER_RADIUS.sm,
                              border: 1,
                              borderColor: 'divider',
                              bgcolor: 'background.paper',
                            }}
                          >
                            <CardContent
                              sx={{ p: 2, '&:last-child': { pb: 2 } }}
                            >
                              <Box sx={{ display: 'flex', gap: 0.5, mb: 1.5 }}>
                                <Skeleton
                                  variant="rounded"
                                  width="20%"
                                  height={24}
                                  sx={{ borderRadius: BORDER_RADIUS.xs }}
                                />
                                <Skeleton
                                  variant="rounded"
                                  width="15%"
                                  height={24}
                                  sx={{ borderRadius: BORDER_RADIUS.xs }}
                                />
                                <Skeleton
                                  variant="rounded"
                                  width="18%"
                                  height={24}
                                  sx={{ borderRadius: BORDER_RADIUS.xs }}
                                />
                              </Box>
                              <Skeleton
                                variant="rounded"
                                width="85%"
                                height={56}
                                sx={{
                                  borderRadius: BORDER_RADIUS.sm,
                                  mb: 1,
                                }}
                              />
                              <Skeleton variant="text" width="40%" />
                            </CardContent>
                          </Card>
                        ))}
                      </Box>
                    )}

                    {/* Load More Button */}
                    {!isLoadingSamples &&
                      !isGenerating &&
                      localTestSamples.length > 0 && (
                        <Box sx={{ textAlign: 'center', mt: 3 }}>
                          <Button
                            variant="outlined"
                            startIcon={
                              isLoadingMore ? (
                                <CircularProgress size={16} />
                              ) : (
                                <AutoFixHighIcon />
                              )
                            }
                            onClick={onLoadMoreSamples}
                            disabled={isLoadingMore}
                          >
                            {isLoadingMore ? 'Loading...' : 'Load More Samples'}
                          </Button>
                        </Box>
                      )}
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>
        </Paper>
      </Box>

      {/* Action Bar — position:relative overrides the default sticky so the
          flex column places it at the bottom of the fixed-height container */}
      <ActionBar
        sx={{ position: 'relative', flexShrink: 0 }}
        leftButton={{
          label: 'Back',
          onClick: onBack,
          variant: 'outlined',
          startIcon: <ArrowBackIcon />,
        }}
        rightButton={{
          label: 'Continue to Confirmation',
          onClick: onNext,
          endIcon: <AutoFixHighIcon />,
        }}
      />

      {/* Endpoint Selection Drawer */}
      <BaseDrawer
        open={showEndpointModal}
        onClose={() => setShowEndpointModal(false)}
        title="Show Live Responses"
        onSave={() => {
          setFetchTrigger(prev => prev + 1);
          setShowEndpointModal(false);
        }}
        saveButtonText={isFetchingResponses ? 'Getting...' : 'Get Responses'}
        saveDisabled={
          !selectedEndpointId ||
          localTestSamples.length === 0 ||
          isFetchingResponses ||
          isLoadingSamples
        }
        closeButtonText="Cancel"
        width={480}
      >
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Select an endpoint to fetch live responses for the test samples.
          </Typography>
          <EndpointSelector
            selectedEndpointId={selectedEndpointId}
            onEndpointChange={onEndpointChange}
            enabled={showEndpointModal}
          />
        </Box>
      </BaseDrawer>
    </Box>
  );
}
