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
          Test Result
        </Typography>

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
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 1,
                          mt: 1,
                        }}
                      >
                        {test.test_output.goal_evaluation.evidence.map(
                          (item, index) => (
                            <Chip
                              key={index}
                              label={item}
                              size="small"
                              variant="outlined"
                              sx={{
                                height: 'auto',
                                py: 0.5,
                                '& .MuiChip-label': {
                                  whiteSpace: 'normal',
                                  textAlign: 'left',
                                },
                              }}
                            />
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
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: testConfig?.instructions
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.instructions ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.instructions || 'No instructions provided'}
                  </Typography>
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
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: testConfig?.restrictions
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.restrictions ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.restrictions || 'No restrictions provided'}
                  </Typography>
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
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: testConfig?.scenario
                        ? 'text.primary'
                        : 'text.secondary',
                      fontStyle: testConfig?.scenario ? 'normal' : 'italic',
                    }}
                  >
                    {testConfig?.scenario || 'No scenario provided'}
                  </Typography>
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
