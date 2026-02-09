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
import {
  getTestResultStatus,
  getTestResultLabel,
} from '@/utils/test-result-status';

interface TestDetailOverviewTabProps {
  test: TestResultDetail;
  prompts: Record<
    string,
    { content: string; name?: string; expected_response?: string }
  >;
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
        <Box
          key={`bullet-${index}`}
          sx={{ display: 'flex', gap: 1, mb: 0.5, pl: 2 }}
        >
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
        test.test_output?.goal_evaluation?.reason ||
        'No evaluation reasoning available'
      );
    }
    return test.test_output?.output || 'No response available';
  }, [isMultiTurn, test]);

  // Get the test result status (Pass, Fail, or Error)
  const testStatus = useMemo(() => getTestResultStatus(test), [test]);
  const testLabel = useMemo(() => getTestResultLabel(test), [test]);

  // Render for Single-turn tests (original simple design)
  if (!isMultiTurn) {
    return (
      <Box sx={{ p: 3 }}>
        {/* Overall Status */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant="h6" fontWeight={600}>
              Test Result
            </Typography>
            <StatusChip
              status={testStatus}
              label={testLabel}
              size="medium"
              variant="filled"
              sx={{ fontWeight: 600 }}
            />
            {/* Show Review Confirmed indicator if review exists */}
            {test.last_review && (
              <Chip
                icon={<CheckIcon sx={{ fontSize: 16 }} />}
                label="Confirmed"
                size="medium"
                color="success"
                variant="filled"
                sx={{
                  fontWeight: 600,
                }}
              />
            )}
          </Box>
        </Box>

        {/* Prompt Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Prompt
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            <Typography
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {promptContent}
            </Typography>
          </Paper>
        </Box>

        {/* Response Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Response
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            <Typography
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {responseContent}
            </Typography>
          </Paper>
        </Box>

        {/* Expected Response Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Expected Response
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            {test.prompt_id && prompts[test.prompt_id]?.expected_response ? (
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {prompts[test.prompt_id].expected_response}
              </Typography>
            ) : (
              <Typography
                variant="body2"
                sx={{ color: 'text.secondary', fontStyle: 'italic' }}
              >
                No expected response provided
              </Typography>
            )}
          </Paper>
        </Box>

        {/* Context Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Context
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            {test.test_output?.context &&
            test.test_output.context.filter(item => item.trim()).length > 0 ? (
              test.test_output.context
                .filter(item => item.trim())
                .map((item, index, filteredArray) => (
                  <Box
                    key={`context-${index}-${item.slice(0, 20)}`}
                    sx={{
                      display: 'flex',
                      gap: 1,
                      mb: index < filteredArray.length - 1 ? 0.5 : 0,
                    }}
                  >
                    <Typography variant="body2">•</Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        flex: 1,
                      }}
                    >
                      {item}
                    </Typography>
                  </Box>
                ))
            ) : (
              <Typography
                variant="body2"
                sx={{ color: 'text.secondary', fontStyle: 'italic' }}
              >
                No context provided
              </Typography>
            )}
          </Paper>
        </Box>

        {/* Tags Section */}
        <Box sx={{ mb: 3 }}>
          <TestResultTags
            sessionToken={sessionToken}
            testResult={test}
            onUpdate={onTestResultUpdate}
          />
        </Box>
      </Box>
    );
  }

  // Render for Multi-turn tests (structured design)
  return (
    <Box sx={{ p: 3 }}>
      {/* Test Result Section */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Test Result
          </Typography>
          <StatusChip
            status={testStatus}
            label={testLabel}
            size="medium"
            variant="filled"
            sx={{ fontWeight: 600 }}
          />
          {/* Show Review Confirmed indicator if review exists */}
          {test.last_review && (
            <Chip
              icon={<CheckIcon sx={{ fontSize: 16 }} />}
              label="Confirmed"
              size="medium"
              color="success"
              variant="filled"
              sx={{
                fontWeight: 600,
              }}
            />
          )}
        </Box>

        {/* Reasoning and Evidence */}
        {test.test_output?.goal_evaluation?.reason && (
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              mb: 2,
            }}
          >
            <Typography
              variant="body2"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                mb: test.test_output?.goal_evaluation?.evidence ? 1.5 : 0,
              }}
            >
              {test.test_output.goal_evaluation.reason}
            </Typography>

            {/* Evidence - Collapsible */}
            {test.test_output?.goal_evaluation?.evidence &&
              test.test_output.goal_evaluation.evidence.length > 0 && (
                <Box>
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

                  <Collapse in={evidenceExpanded} timeout="auto" unmountOnExit>
                    <Box sx={{ mt: 1, pl: 2 }}>
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
                              }}
                            >
                              •
                            </Typography>
                            <Typography
                              variant="body2"
                              sx={{
                                color: 'text.secondary',
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
          </Paper>
        )}
      </Box>

      {/* Divider */}
      <Divider sx={{ mb: 3 }} />

      {/* Goal Section */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={600} gutterBottom>
          Goal
        </Typography>
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: theme.palette.background.default,
            maxHeight: 200,
            overflow: 'auto',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {promptContent}
          </Typography>
        </Paper>
      </Box>

      {/* Instructions */}
      {testConfig?.instructions && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Instructions
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            {renderFormattedText(testConfig.instructions)}
          </Paper>
        </Box>
      )}

      {/* Restrictions */}
      {testConfig?.restrictions && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Restrictions
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            {renderFormattedText(testConfig.restrictions)}
          </Paper>
        </Box>
      )}

      {/* Scenario */}
      {testConfig?.scenario && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            Scenario
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 2,
              backgroundColor: theme.palette.background.default,
              maxHeight: 200,
              overflow: 'auto',
            }}
          >
            {renderFormattedText(testConfig.scenario)}
          </Paper>
        </Box>
      )}
    </Box>
  );
}
