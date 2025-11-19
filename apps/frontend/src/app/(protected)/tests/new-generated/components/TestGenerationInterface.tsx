'use client';

import React, { useState, useCallback, useEffect } from 'react';
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
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SendIcon from '@mui/icons-material/Send';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DescriptionIcon from '@mui/icons-material/Description';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import ApiIcon from '@mui/icons-material/Api';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import RefreshIcon from '@mui/icons-material/Refresh';
import { ConfigChips, TestSample, ChatMessage } from './shared/types';
import { SourceData } from '@/utils/api-client/interfaces/test-set';
import ChipGroup from './shared/ChipGroup';
import TestSampleCard from './shared/TestSampleCard';
import ActionBar from '@/components/common/ActionBar';
import EndpointSelector from './shared/EndpointSelector';
import UploadSourceDialog from '../../../knowledge/components/UploadSourceDialog';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface TestGenerationInterfaceProps {
  configChips: ConfigChips;
  testSamples: TestSample[];
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
  onSamplesUpdate?: (samples: TestSample[]) => void;
}

/**
 * TestGenerationInterface Component
 * 2-panel interface with configuration on left and preview on right
 */
export default function TestGenerationInterface({
  configChips,
  testSamples,
  chatMessages,
  description,
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
  const [endpointInfo, setEndpointInfo] = useState<{
    name: string;
    projectName: string;
    environment: string;
  } | null>(null);
  const [localTestSamples, setLocalTestSamples] =
    useState<TestSample[]>(testSamples);
  const [isFetchingResponses, setIsFetchingResponses] = useState(false);
  const [processedSampleIds, setProcessedSampleIds] = useState<Set<string>>(
    new Set()
  );
  const [showEndpointModal, setShowEndpointModal] = useState(false);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const { data: session } = useSession();

  // Sync local samples with prop changes - merge new samples while preserving existing responses
  useEffect(() => {
    if (testSamples.length === 0) {
      setLocalTestSamples([]);
      return;
    }

    // Create a map of existing samples with responses
    const existingSamplesMap = new Map(
      localTestSamples.map(sample => [sample.id, sample])
    );

    // Merge: keep existing samples with responses, add new samples
    const mergedSamples = testSamples.map(newSample => {
      const existingSample = existingSamplesMap.get(newSample.id);

      // If sample exists and has response data, keep it
      if (
        existingSample &&
        (existingSample.response ||
          existingSample.isLoadingResponse ||
          existingSample.responseError)
      ) {
        return existingSample;
      }

      // Otherwise use the new sample from props
      return newSample;
    });

    setLocalTestSamples(mergedSamples);
  }, [testSamples]);

  // Load endpoint information when selectedEndpointId changes
  useEffect(() => {
    const loadEndpointInfo = async () => {
      if (!selectedEndpointId || !session?.session_token) {
        setEndpointInfo(null);
        return;
      }

      try {
        // Create API clients
        const apiFactory = new ApiClientFactory(session.session_token);
        const endpointsClient = apiFactory.getEndpointsClient();
        const projectsClient = apiFactory.getProjectsClient();

        const endpoint = await endpointsClient.getEndpoint(selectedEndpointId);

        // Fetch project name if available
        let projectName = 'Unknown Project';
        if (endpoint.project_id) {
          try {
            const project = await projectsClient.getProject(
              endpoint.project_id
            );
            projectName = project.name;
          } catch (err) {}
        }

        setEndpointInfo({
          name: endpoint.name,
          projectName,
          environment: endpoint.environment,
        });
      } catch (error) {
        setEndpointInfo(null);
      }
    };

    // Reset processed IDs and clear responses when endpoint changes
    setProcessedSampleIds(new Set());

    // Clear existing responses from samples whenever endpoint changes (including when set to null)
    setLocalTestSamples(prev =>
      prev.map(sample => {
        const newSample = { ...sample };
        delete newSample.response;
        delete newSample.responseError;
        delete newSample.isLoadingResponse;
        return newSample;
      })
    );

    loadEndpointInfo();
  }, [selectedEndpointId, session]);

  // Fetch responses from endpoint for all samples
  useEffect(() => {
    const fetchResponses = async () => {
      if (
        !selectedEndpointId ||
        !session?.session_token ||
        localTestSamples.length === 0 ||
        isFetchingResponses
      ) {
        return;
      }

      // Find samples that haven't been processed yet
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

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const endpointsClient = apiFactory.getEndpointsClient();

        // Mark samples to fetch as loading
        const updatedSamples = localTestSamples.map(sample => {
          if (samplesToFetch.some(s => s.id === sample.id)) {
            const newSample = {
              ...sample,
              isLoadingResponse: true,
            };
            delete newSample.response;
            delete newSample.responseError;
            return newSample;
          }
          return sample;
        });
        setLocalTestSamples(updatedSamples);

        // Fetch responses for each new sample
        const newProcessedIds = new Set(processedSampleIds);

        for (let i = 0; i < updatedSamples.length; i++) {
          const sample = updatedSamples[i];

          // Skip samples that were already processed or not in the fetch list
          if (!samplesToFetch.some(s => s.id === sample.id)) {
            continue;
          }

          try {
            // Invoke the endpoint with the sample's prompt
            const response = await endpointsClient.invokeEndpoint(
              selectedEndpointId,
              {
                input: sample.prompt,
              }
            );

            // Extract response text from various possible response formats
            let responseText = '';
            if (typeof response === 'string') {
              responseText = response;
            } else if (response?.output) {
              responseText = response.output;
            } else if (response?.text) {
              responseText = response.text;
            } else if (response?.response) {
              responseText = response.response;
            } else if (response?.content) {
              responseText = response.content;
            } else {
              responseText = JSON.stringify(response);
            }

            updatedSamples[i] = {
              ...sample,
              response: responseText,
              isLoadingResponse: false,
            };
            delete updatedSamples[i].responseError;
            newProcessedIds.add(sample.id);
          } catch (error) {
            updatedSamples[i] = {
              ...sample,
              isLoadingResponse: false,
              responseError:
                error instanceof Error
                  ? error.message
                  : 'Failed to fetch response',
            };
            delete updatedSamples[i].response;
            newProcessedIds.add(sample.id);
          }

          // Update state after each response to show progress
          setLocalTestSamples([...updatedSamples]);
        }

        // Update processed IDs
        setProcessedSampleIds(newProcessedIds);

        // Notify parent component of updates if callback provided
        if (onSamplesUpdate) {
          onSamplesUpdate(updatedSamples);
        }
      } finally {
        setIsFetchingResponses(false);
      }
    };

    fetchResponses();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEndpointId, session?.session_token, localTestSamples.length]);

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

  return (
    <Box sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
      {/* Main Content */}
      <Box
        sx={{
          pt: 3,
          pb: 3,
        }}
      >
        {/* 2 Panel Layout */}
        <Paper
          elevation={2}
          sx={{
            display: 'flex',
            height: 'calc(100vh - 200px)',
            overflow: 'hidden',
            mb: 4,
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
                      Tests Configuration
                    </Typography>
                    <Tooltip
                      title="Configure test parameters and upload sources to guide AI generation."
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
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
                {/* Loading Overlay */}
                {(isLoadingConfig || isGenerating) && (
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      bgcolor: 'background.paper',
                      opacity: 0.95,
                      zIndex: 1,
                    }}
                  >
                    <CircularProgress sx={{ mb: 2 }} />
                    <Typography variant="body1">
                      {isLoadingConfig ? 'Loading configuration...' : 'Updating configuration...'}
                    </Typography>
                  </Box>
                )}

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
                  <Tooltip title="Upload source">
                    <IconButton
                      size="small"
                      sx={{ ml: 0.5 }}
                      onClick={() => setShowUploadDialog(true)}
                    >
                      <AddIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
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
                      color: 'white',
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
              bgcolor: 'background.default',
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
                }}
                title={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h6" fontWeight="bold">
                      Review Test Cases
                    </Typography>
                    <Tooltip
                      title="Preview of generated test samples. Rate them to improve future generations."
                      arrow
                      placement="top"
                    >
                      <InfoOutlinedIcon
                        sx={{
                          fontSize: 16,
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
                      startIcon={endpointInfo ? <SwapHorizIcon /> : <ApiIcon />}
                      onClick={() => setShowEndpointModal(true)}
                      sx={{ textTransform: 'none' }}
                    >
                      {endpointInfo
                        ? `${endpointInfo.projectName} › ${endpointInfo.name}`
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
                  bgcolor: 'background.default',
                  overflow: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {(isLoadingSamples || isGenerating) ? (
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flex: 1,
                    }}
                  >
                    <CircularProgress sx={{ mb: 2 }} />
                    <Typography variant="body1">
                      {isLoadingSamples ? 'Loading test samples...' : 'Generating test samples...'}
                    </Typography>
                  </Box>
                ) : localTestSamples.length === 0 ? (
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
                      sx={{ fontSize: 64, opacity: 0.3, mb: 2 }}
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
                        onRate={onRateSample}
                        onFeedbackChange={onSampleFeedbackChange}
                        onRegenerate={onRegenerate}
                        isRegenerating={regeneratingSampleId === sample.id}
                      />
                    ))}

                    {/* Load More Button */}
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
                  </Box>
                )}
              </CardContent>
            </Card>
          </Box>
        </Paper>
      </Box>

      {/* Action Bar */}
      <ActionBar
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

      {/* Endpoint Selection Modal */}
      <Dialog
        open={showEndpointModal}
        onClose={() => setShowEndpointModal(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Select Endpoint for Test Preview</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Test samples will show live responses from this endpoint.
            </Typography>
            <EndpointSelector
              selectedEndpointId={selectedEndpointId}
              onEndpointChange={onEndpointChange}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowEndpointModal(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Upload Source Dialog */}
      {session?.session_token && (
        <UploadSourceDialog
          open={showUploadDialog}
          onClose={() => setShowUploadDialog(false)}
          sessionToken={session.session_token}
        />
      )}
    </Box>
  );
}
