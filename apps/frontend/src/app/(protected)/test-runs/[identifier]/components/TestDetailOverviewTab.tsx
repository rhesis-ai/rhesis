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
import ConversationHistory from '@/components/common/ConversationHistory';
import {
  getTestResultStatus,
  getTestResultLabel,
} from '@/utils/testResultStatus';

interface TestDetailOverviewTabProps {
  test: TestResultDetail;
  prompts: Record<string, { content: string; name?: string }>;
  sessionToken: string;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
}

// Helper function to render text with proper list formatting
const renderFormattedText = (text: string) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentParagraph: string[] = [];

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();
    
    // Check if line starts with a dash (bullet point)
    if (trimmedLine.startsWith('- ')) {
      // Flush current paragraph if exists
      if (currentParagraph.length > 0) {
        elements.push(
          <Typography key={`p-${index}`} variant="body2" sx={{ mb: 1 }}>
            {currentParagraph.join(' ')}
          </Typography>
        );
        currentParagraph = [];
      }
      
      // Add bullet point
      elements.push(
        <Box key={`bullet-${index}`} sx={{ display: 'flex', gap: 1, mb: 0.5, pl: 2 }}>
          <Typography variant="body2">•</Typography>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {trimmedLine.substring(2).trim()}
          </Typography>
        </Box>
      );
    } else if (trimmedLine) {
      // Non-empty line without dash
      currentParagraph.push(trimmedLine);
    } else if (currentParagraph.length > 0) {
      // Empty line - flush paragraph
      elements.push(
        <Typography key={`p-${index}`} variant="body2" sx={{ mb: 1 }}>
          {currentParagraph.join(' ')}
        </Typography>
      );
      currentParagraph = [];
    }
  });

  // Flush remaining paragraph
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
  sessionToken,
  onTestResultUpdate,
  testSetType,
}: TestDetailOverviewTabProps) {
  const theme = useTheme();
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);

  // Determine if this is a multi-turn test
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  // Get test configuration from test_output (multi-turn data lives here)
  const testConfig = test.test_output?.test_configuration;

  // Get content based on test type
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
        test.test_output?.goal_evaluation?.reasoning ||
        'No evaluation reasoning available'
      );
    }
    return test.test_output?.output || 'No response available';
  }, [isMultiTurn, test]);

  // Get the test result status (Pass, Fail, or Error)
  const testStatus = useMemo(() => getTestResultStatus(test), [test]);
  const testLabel = useMemo(() => getTestResultLabel(test), [test]);

  return (
    <Box sx={{ p: 3 }}>
      {/* Test Result Section */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Typography
            variant="overline"
            sx={{
              color: 'text.secondary',
              fontWeight: 600,
              letterSpacing: 1,
            }}
          >
            Test Result
          </Typography>
          
          {/* Show Review Confirmed indicator if review exists */}
          {test.last_review && (
            <Chip
              icon={<CheckIcon sx={{ fontSize: 14 }} />}
              label="Review Confirmed"
              size="small"
              sx={{
                bgcolor: theme.palette.mode === 'light' ? '#E8F5E9' : '#1B2F1E',
                color: theme.palette.success.main,
                fontWeight: 500,
                border: `1px solid ${theme.palette.mode === 'light' ? '#A5D6A7' : '#2E7D32'}`,
                height: '20px',
              }}
            />
          )}
        </Box>

        <Paper
          variant="outlined"
          sx={{
            p: 2.5,
            backgroundColor: theme.palette.background.default,
          }}
        >
          {/* Status and Reasoning in one line */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            <StatusChip
              status={testStatus}
              label={testLabel}
              size="medium"
              variant="filled"
              sx={{ fontWeight: 600, flexShrink: 0 }}
            />

            {/* Reasoning and Evidence Container */}
            <Box sx={{ flex: 1 }}>
              {/* Reasoning (Multi-turn only) */}
              {isMultiTurn && test.test_output?.goal_evaluation?.reasoning && (
                <Typography
                  variant="body2"
                  sx={{
                    color: 'text.secondary',
                    lineHeight: 1.6,
                    mb: 1.5,
                  }}
                >
                  {test.test_output.goal_evaluation.reasoning}
                </Typography>
              )}

              {/* Evidence (Multi-turn only) - Collapsible */}
              {isMultiTurn &&
                test.test_output?.goal_evaluation?.evidence &&
                test.test_output.goal_evaluation.evidence.length > 0 && (
                  <Box>
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
                      <Box
                        sx={{
                          mt: 1,
                          pl: 2,
                        }}
                      >
                        {test.test_output.goal_evaluation.evidence.map(
                          (item, index) => (
                            <Box
                              key={index}
                              sx={{
                                display: 'flex',
                                gap: 1,
                                mb: 0.5,
                              }}
                            >
                              <Typography
                                variant="body2"
                                sx={{
                                  color: 'text.secondary',
                                  fontSize: '0.875rem',
                                }}
                              >
                                •
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{
                                  color: 'text.secondary',
                                  fontSize: '0.875rem',
                                  flex: 1,
                                }}
                              >
                                {item}
                              </Typography>
                            </Box>
                          )
                        )}
                      </Box>
                    </Collapse>
                  </Box>
                )}
            </Box>
          </Box>
        </Paper>
      </Box>

      {/* Divider between Result and Configuration */}
      <Divider sx={{ my: 4 }} />

      {/* Test Configuration Section */}
      <Box>
        <Typography
          variant="overline"
          sx={{
            color: 'text.secondary',
            fontWeight: 600,
            letterSpacing: 1,
            display: 'block',
            mb: 2,
          }}
        >
          Test Configuration
        </Typography>

        <Paper
          variant="outlined"
          sx={{
            p: 2.5,
            backgroundColor: theme.palette.background.default,
          }}
        >
          {/* Goal/Prompt */}
          <Box sx={{ mb: 2 }}>
            <Typography
              variant="caption"
              sx={{
                color: 'text.secondary',
                fontWeight: 600,
                display: 'block',
                mb: 0.5,
              }}
            >
              {isMultiTurn ? 'Goal' : 'Prompt'}
            </Typography>
            <Typography
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {promptContent}
            </Typography>
          </Box>

          {/* Multi-turn Configuration Details */}
          {isMultiTurn && (
            <>
              {/* Instructions */}
              {(testConfig?.instructions || true) && (
                <Box sx={{ mb: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      fontWeight: 600,
                      display: 'block',
                      mb: 0.5,
                    }}
                  >
                    Instructions
                  </Typography>
                  <Box
                    sx={{
                      color: testConfig?.instructions
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.instructions ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.instructions 
                      ? renderFormattedText(testConfig.instructions)
                      : <Typography variant="body2">No instructions provided</Typography>
                    }
                  </Box>
                </Box>
              )}

              {/* Restrictions */}
              {(testConfig?.restrictions || true) && (
                <Box sx={{ mb: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      fontWeight: 600,
                      display: 'block',
                      mb: 0.5,
                    }}
                  >
                    Restrictions
                  </Typography>
                  <Box
                    sx={{
                      color: testConfig?.restrictions
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.restrictions ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.restrictions 
                      ? renderFormattedText(testConfig.restrictions)
                      : <Typography variant="body2">No restrictions provided</Typography>
                    }
                  </Box>
                </Box>
              )}

              {/* Scenario */}
              {(testConfig?.scenario || true) && (
                <Box sx={{ mb: 0 }}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      fontWeight: 600,
                      display: 'block',
                      mb: 0.5,
                    }}
                  >
                    Scenario
                  </Typography>
                  <Box
                    sx={{
                      color: testConfig?.scenario
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.scenario ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.scenario 
                      ? renderFormattedText(testConfig.scenario)
                      : <Typography variant="body2">No scenario provided</Typography>
                    }
                  </Box>
                </Box>
              )}
            </>
          )}

          {/* Response Section (Single-turn only) */}
          {!isMultiTurn && (
            <Box sx={{ mb: 0 }}>
              <Typography
                variant="caption"
                sx={{
                  color: 'text.secondary',
                  fontWeight: 600,
                  display: 'block',
                  mb: 0.5,
                }}
              >
                Response
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {responseContent}
              </Typography>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  );
}
