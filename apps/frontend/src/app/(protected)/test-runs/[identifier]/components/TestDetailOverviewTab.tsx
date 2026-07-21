'use client';

import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  useTheme,
  Divider,
  Collapse,
  IconButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckIcon from '@mui/icons-material/Check';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestResultTags from './TestResultTags';
import StatusChip from '@/components/common/StatusChip';
import ViewField from '@/components/common/ViewField';
import FileAttachmentList from '@/components/common/FileAttachmentList';
import { useFiles } from '@/hooks/useFiles';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

interface TestDetailOverviewTabProps {
  test: TestResultDetail;
  prompts: Record<
    string,
    { content: string; name?: string; expected_response?: string }
  >;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
}

// Try to parse a string as JSON and pretty-print it; returns null if not JSON
const tryFormatJson = (text: string): string | null => {
  const trimmed = text.trim();
  if (
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  ) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      return null;
    }
  }
  return null;
};

// Helper function to render text with proper list formatting
const renderFormattedText = (text: string) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentParagraph: string[] = [];

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith('- ')) {
      if (currentParagraph.length > 0) {
        const paragraphKey = `p-${index}-${currentParagraph.join(' ').substring(0, 20)}`;
        elements.push(
          <Typography key={paragraphKey} variant="body2" sx={{ mb: 1 }}>
            {currentParagraph.join(' ')}
          </Typography>
        );
        currentParagraph = [];
      }

      const bulletKey = `bullet-${index}-${trimmedLine.substring(0, 20)}`;
      elements.push(
        <Box key={bulletKey} sx={{ display: 'flex', gap: 1, mb: 0.5, pl: 2 }}>
          <Typography variant="body2">•</Typography>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {trimmedLine.substring(2).trim()}
          </Typography>
        </Box>
      );
    } else if (trimmedLine) {
      currentParagraph.push(trimmedLine);
    } else if (currentParagraph.length > 0) {
      const paragraphKey = `p-${index}-${currentParagraph.join(' ').substring(0, 20)}`;
      elements.push(
        <Typography key={paragraphKey} variant="body2" sx={{ mb: 1 }}>
          {currentParagraph.join(' ')}
        </Typography>
      );
      currentParagraph = [];
    }
  });

  if (currentParagraph.length > 0) {
    elements.push(
      <Typography key="p-final" variant="body2">
        {currentParagraph.join(' ')}
      </Typography>
    );
  }

  return <>{elements}</>;
};

export default function TestDetailOverviewTab({
  test,
  prompts,
  onTestResultUpdate,
  testSetType,
}: TestDetailOverviewTabProps) {
  const theme = useTheme();
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const [metadataExpanded, setMetadataExpanded] = useState(false);
  const [filesExpanded, setFilesExpanded] = useState(false);
  const [outputFilesExpanded, setOutputFilesExpanded] = useState(false);

  const { files: testFiles, isLoading: testFilesLoading } = useFiles({
    entityId: (test.test_id as string) || '',
    entityType: 'Test',
  });

  const { files: outputFiles, isLoading: outputFilesLoading } = useFiles({
    entityId: test.id as string,
    entityType: 'TestResult',
  });

  // Render text content, formatting JSON when detected
  const renderTextContent = (text: string) => {
    const formatted = tryFormatJson(text);
    if (formatted) {
      return (
        <Typography
          component="pre"
          variant="body2"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: theme.typography.fontFamilyCode,
            m: 0,
          }}
        >
          {formatted}
        </Typography>
      );
    }
    return (
      <Typography
        variant="body2"
        sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
      >
        {text}
      </Typography>
    );
  };

  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;
  const expectedResponse = test.prompt_id
    ? prompts[test.prompt_id]?.expected_response
    : undefined;

  const testConfig = test.test_output?.test_configuration;

  const promptContent = useMemo(() => {
    if (isMultiTurn) {
      return testConfig?.goal || 'No goal available';
    }
    return test.prompt_id && prompts[test.prompt_id]
      ? prompts[test.prompt_id].content
      : test.test?.prompt?.content || 'No prompt available';
  }, [isMultiTurn, test, prompts, testConfig]);

  const responseContent = useMemo(() => {
    if (isMultiTurn) {
      return (
        test.test_output?.goal_evaluation?.reason ||
        'No evaluation reasoning available'
      );
    }
    return test.test_output?.output || 'No response available';
  }, [isMultiTurn, test]);

  const testStatus = useMemo(() => getEffectiveTestResultStatus(test), [test]);
  const testLabel = useMemo(() => {
    switch (testStatus) {
      case 'Pass':
        return 'Passed';
      case 'Fail':
        return 'Failed';
      case 'Error':
        return 'Error';
      default:
        return 'Unknown';
    }
  }, [testStatus]);

  // Shared status header used in both branches
  const statusHeader = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
      <Typography variant="body2" color="text.secondary">
        Status
      </Typography>
      <StatusChip
        status={testStatus}
        label={testLabel}
        size="small"
        variant="outlined"
      />
      {test.last_review && (
        <Chip
          icon={<CheckIcon sx={{ fontSize: 16 }} />}
          label="Confirmed"
          size="small"
          color="success"
          variant="filled"
          sx={{ fontWeight: 600 }}
        />
      )}
    </Box>
  );

  // Shared card styling matching Figma "Data Output Textfield" card
  const cardSx = {
    p: '30px',
    borderRadius: BORDER_RADIUS.md,
    boxShadow: ELEVATION.xs,
    mb: 3,
  };

  // Single-turn render
  if (!isMultiTurn) {
    const contextItems =
      test.test_output?.context?.filter(item => item.trim()) ?? [];

    return (
      <Box sx={{ p: 3 }}>
        {statusHeader}

        <Paper variant="outlined" sx={cardSx}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {/* Prompt — full width */}
            <ViewField label="Prompt" multiline>
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                {renderTextContent(promptContent)}
              </Box>
            </ViewField>

            {/* Response + Expected Response — side by side */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Box sx={{ flex: 1 }}>
                <ViewField label="Response" multiline>
                  <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                    {renderTextContent(responseContent)}
                  </Box>
                </ViewField>
              </Box>
              <Box sx={{ flex: 1 }}>
                <ViewField label="Expected Response" multiline>
                  <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                    {expectedResponse ? (
                      renderTextContent(expectedResponse)
                    ) : (
                      <Typography
                        variant="body2"
                        sx={{ color: 'text.secondary', fontStyle: 'italic' }}
                      >
                        No expected response provided
                      </Typography>
                    )}
                  </Box>
                </ViewField>
              </Box>
            </Box>

            {/* Context — always expanded when present */}
            {contextItems.length > 0 && (
              <ViewField label={`Context (${contextItems.length})`} multiline>
                <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                  {contextItems.map((item, index, arr) => {
                    const contextKey = `context-${item.slice(0, 30).replace(/\s+/g, '-')}`;
                    return (
                      <Box
                        key={contextKey}
                        sx={{
                          display: 'flex',
                          gap: 1,
                          mb: index < arr.length - 1 ? 0.5 : 0,
                        }}
                      >
                        <Typography variant="body2">•</Typography>
                        <Box sx={{ flex: 1 }}>{renderTextContent(item)}</Box>
                      </Box>
                    );
                  })}
                </Box>
              </ViewField>
            )}

            {/* Tags */}
            <TestResultTags testResult={test} onUpdate={onTestResultUpdate} />
          </Box>
        </Paper>

        {/* Metadata Section (collapsible) */}
        {test.test_output?.metadata &&
          Object.keys(test.test_output.metadata).length > 0 && (
            <Box sx={{ mb: 3 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  cursor: 'pointer',
                  mb: 1,
                  '&:hover': { opacity: 0.7 },
                }}
                onClick={() => setMetadataExpanded(!metadataExpanded)}
              >
                <Typography variant="subtitle2" fontWeight={600}>
                  Metadata
                </Typography>
                <IconButton
                  size="small"
                  sx={{
                    padding: 0,
                    transform: metadataExpanded
                      ? 'rotate(180deg)'
                      : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                  }}
                >
                  <ExpandMoreIcon sx={{ fontSize: 18 }} />
                </IconButton>
              </Box>
              <Collapse in={metadataExpanded} timeout="auto" unmountOnExit>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    backgroundColor: theme.palette.background.default,
                    maxHeight: 300,
                    overflow: 'auto',
                  }}
                >
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: theme.typography.fontFamilyCode,
                      m: 0,
                    }}
                  >
                    {JSON.stringify(test.test_output.metadata, null, 2)}
                  </Typography>
                </Paper>
              </Collapse>
            </Box>
          )}

        {/* Files Section (collapsible) */}
        {(testFilesLoading || testFiles.length > 0) && (
          <Box sx={{ mb: 3 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                mb: 1,
                '&:hover': { opacity: 0.7 },
              }}
              onClick={() => setFilesExpanded(!filesExpanded)}
            >
              <Typography variant="subtitle2" fontWeight={600}>
                Files ({testFiles.length})
              </Typography>
              <IconButton
                size="small"
                sx={{
                  padding: 0,
                  transform: filesExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                }}
              >
                <ExpandMoreIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Box>
            <Collapse in={filesExpanded} timeout="auto" unmountOnExit>
              <FileAttachmentList
                files={testFiles}
                isLoading={testFilesLoading}
              />
            </Collapse>
          </Box>
        )}

        {/* Output Files Section (collapsible) */}
        {(outputFilesLoading || outputFiles.length > 0) && (
          <Box sx={{ mb: 3 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                cursor: 'pointer',
                mb: 1,
                '&:hover': { opacity: 0.7 },
              }}
              onClick={() => setOutputFilesExpanded(!outputFilesExpanded)}
            >
              <Typography variant="subtitle2" fontWeight={600}>
                Output Files ({outputFiles.length})
              </Typography>
              <IconButton
                size="small"
                sx={{
                  padding: 0,
                  transform: outputFilesExpanded
                    ? 'rotate(180deg)'
                    : 'rotate(0deg)',
                  transition: 'transform 0.2s',
                }}
              >
                <ExpandMoreIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Box>
            <Collapse in={outputFilesExpanded} timeout="auto" unmountOnExit>
              <FileAttachmentList
                files={outputFiles}
                isLoading={outputFilesLoading}
              />
            </Collapse>
          </Box>
        )}
      </Box>
    );
  }

  // Multi-turn render
  return (
    <Box sx={{ p: 3 }}>
      {statusHeader}

      <Paper variant="outlined" sx={cardSx}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {/* Goal */}
          <ViewField label="Goal" multiline>
            <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
              <Typography
                variant="body2"
                sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {promptContent}
              </Typography>
            </Box>
          </ViewField>

          {/* Instructions */}
          {testConfig?.instructions && (
            <ViewField label="Instructions" multiline>
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                {renderFormattedText(testConfig.instructions)}
              </Box>
            </ViewField>
          )}

          {/* Restrictions */}
          {testConfig?.restrictions && (
            <ViewField label="Restrictions" multiline>
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                {renderFormattedText(testConfig.restrictions)}
              </Box>
            </ViewField>
          )}

          {/* Scenario */}
          {testConfig?.scenario && (
            <ViewField label="Scenario" multiline>
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                {renderFormattedText(testConfig.scenario)}
              </Box>
            </ViewField>
          )}

          {/* Reasoning & Evidence */}
          {test.test_output?.goal_evaluation?.reason && (
            <Box>
              <ViewField label="Reasoning" multiline>
                <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                  <Typography
                    variant="body2"
                    sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                  >
                    {test.test_output.goal_evaluation.reason}
                  </Typography>
                </Box>
              </ViewField>

              {/* Evidence — collapsible */}
              {test.test_output?.goal_evaluation?.evidence &&
                test.test_output.goal_evaluation.evidence.length > 0 && (
                  <Box sx={{ mt: 1.5 }}>
                    <Divider sx={{ mb: 1.5 }} />
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        cursor: 'pointer',
                        '&:hover': { opacity: 0.7 },
                      }}
                      onClick={() => setEvidenceExpanded(!evidenceExpanded)}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: 'text.secondary',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                          letterSpacing: 0.5,
                        }}
                      >
                        {evidenceExpanded ? 'Hide' : 'Show'} Evidence (
                        {test.test_output.goal_evaluation.evidence.length})
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          padding: 0,
                          transform: evidenceExpanded
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                        }}
                      >
                        <ExpandMoreIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </Box>

                    <Collapse
                      in={evidenceExpanded}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Box sx={{ mt: 1, pl: 2 }}>
                        {test.test_output.goal_evaluation.evidence.map(
                          (item, index) => {
                            const evidenceKey = `evidence-${index}-${item.substring(0, 30).replace(/\s+/g, '-')}`;
                            return (
                              <Box
                                key={evidenceKey}
                                sx={{ display: 'flex', gap: 1, mb: 0.5 }}
                              >
                                <Typography
                                  variant="body2"
                                  sx={{ color: 'text.secondary' }}
                                >
                                  •
                                </Typography>
                                <Typography
                                  variant="body2"
                                  sx={{ color: 'text.secondary', flex: 1 }}
                                >
                                  {item}
                                </Typography>
                              </Box>
                            );
                          }
                        )}
                      </Box>
                    </Collapse>
                  </Box>
                )}
            </Box>
          )}

          {/* Tags */}
          <TestResultTags testResult={test} onUpdate={onTestResultUpdate} />
        </Box>
      </Paper>

      {/* Files Section (collapsible) */}
      {(testFilesLoading || testFiles.length > 0) && (
        <Box sx={{ mb: 3 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              cursor: 'pointer',
              mb: 1,
              '&:hover': { opacity: 0.7 },
            }}
            onClick={() => setFilesExpanded(!filesExpanded)}
          >
            <Typography variant="subtitle2" fontWeight={600}>
              Files ({testFiles.length})
            </Typography>
            <IconButton
              size="small"
              sx={{
                padding: 0,
                transform: filesExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s',
              }}
            >
              <ExpandMoreIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Box>
          <Collapse in={filesExpanded} timeout="auto" unmountOnExit>
            <FileAttachmentList
              files={testFiles}
              isLoading={testFilesLoading}
            />
          </Collapse>
        </Box>
      )}

      {/* Output Files Section (collapsible) */}
      {(outputFilesLoading || outputFiles.length > 0) && (
        <Box sx={{ mb: 3 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              cursor: 'pointer',
              mb: 1,
              '&:hover': { opacity: 0.7 },
            }}
            onClick={() => setOutputFilesExpanded(!outputFilesExpanded)}
          >
            <Typography variant="subtitle2" fontWeight={600}>
              Output Files ({outputFiles.length})
            </Typography>
            <IconButton
              size="small"
              sx={{
                padding: 0,
                transform: outputFilesExpanded
                  ? 'rotate(180deg)'
                  : 'rotate(0deg)',
                transition: 'transform 0.2s',
              }}
            >
              <ExpandMoreIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Box>
          <Collapse in={outputFilesExpanded} timeout="auto" unmountOnExit>
            <FileAttachmentList
              files={outputFiles}
              isLoading={outputFilesLoading}
            />
          </Collapse>
        </Box>
      )}
    </Box>
  );
}
