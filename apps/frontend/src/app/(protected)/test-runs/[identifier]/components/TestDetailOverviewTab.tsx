'use client';

import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  useTheme,
  Collapse,
  Divider,
  IconButton,
  Alert,
  AlertTitle,
  Link,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckIcon from '@mui/icons-material/Check';
import EditIcon from '@mui/icons-material/Edit';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestResultTags from './TestResultTags';
import StatusChip from '@/components/common/StatusChip';
import ViewField from '@/components/common/ViewField';
import FileAttachmentList from '@/components/common/FileAttachmentList';
import MarkdownContent from '@/components/common/MarkdownContent';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';
import { useFiles } from '@/hooks/useFiles';
import {
  getEffectiveTestResultStatus,
  hasConflictingAnnotation,
} from '@/utils/test-result-status';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import { MetricsSource } from '@/utils/api-client/interfaces/test-configuration';
import { buildResultChecks, checksSummary } from '@/utils/result-checks';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

interface TestDetailOverviewTabProps {
  test: TestResultDetail;
  prompts: Record<
    string,
    { content: string; name?: string; expected_response?: string }
  >;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
  /** Source of metrics used in this test run */
  metricsSource?: MetricsSource | string;
  onShowEvaluation?: () => void;
}

// Helper function to render text with proper list formatting
const renderFormattedText = (text: string) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentParagraph: string[] = [];

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    const numbered = /^(\d+)[.)]\s+(.*)$/.exec(trimmedLine);
    if (trimmedLine.startsWith('- ') || numbered) {
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
          <Typography variant="body2">
            {numbered ? `${numbered[1]}.` : '•'}
          </Typography>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {numbered ? numbered[2] : trimmedLine.substring(2).trim()}
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

/** A small uppercase label over plain text, lighter than ViewField's filled box. */
function SectionField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const theme = useTheme();
  return (
    <Box>
      <Typography
        variant="caption"
        component="h4"
        color="text.secondary"
        sx={{
          display: 'block',
          mb: 0.75,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: theme.typography.overline.letterSpacing,
        }}
      >
        {label}
      </Typography>
      {children}
    </Box>
  );
}

const ABBREVIATION = /\b(e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|No)\.$/i;

/**
 * One line of separate sentences ("Must not X. Must not Y.") as "- " lines, so
 * renderFormattedText lists them. Text that already has lines is left alone.
 */
export function asSentenceList(text: string): string {
  if (text.includes('\n')) return text;
  const sentences = text
    .trim()
    // A line break after each sentence end, then split on it: no regex lookbehind needed.
    .replace(/([.!?])\s+(?=[A-Z])/g, '$1\n')
    .split('\n')
    .reduce<string[]>((acc, part) => {
      const prev = acc[acc.length - 1];
      if (prev && ABBREVIATION.test(prev))
        acc[acc.length - 1] = `${prev} ${part}`;
      else acc.push(part);
      return acc;
    }, []);
  return sentences.length > 1 ? sentences.map(x => `- ${x}`).join('\n') : text;
}

export default function TestDetailOverviewTab({
  test,
  prompts,
  onTestResultUpdate,
  testSetType,
  metricsSource,
  onShowEvaluation,
}: TestDetailOverviewTabProps) {
  const theme = useTheme();
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

  const renderTextContent = (text: string) => {
    const parsed = parseJsonString(text);
    if (parsed !== null) {
      return (
        <Box
          component="pre"
          sx={{
            fontFamily: 'monospace',
            fontSize: 12,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            m: 0,
            p: 0,
          }}
        >
          <JsonPreview value={parsed} />
        </Box>
      );
    }
    return looksLikeMarkdown(text) ? (
      <MarkdownContent content={text} variant="body2" />
    ) : (
      <Typography
        variant="body2"
        sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
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

  // Non-null when the target rejected or never answered the call. Everything the endpoint
  // did say about why lives in here; see utils/endpoint-failure.ts.
  const endpointFailure = useMemo(
    () => getEndpointFailure(test.test_output),
    [test.test_output]
  );

  // `error` is a boolean flag on an invoker result and prose on a multi-turn contract
  // failure, so only the prose form is usable as display text. Rendering the flag would
  // put a bare "true" in the Response field.
  const contractError =
    typeof test.test_output?.error === 'string'
      ? test.test_output.error
      : undefined;

  const responseContent = useMemo(() => {
    if (isMultiTurn) {
      // goal_evaluation.reason is absent when no metric ran at all -- e.g. the evaluation
      // contract was stale or too ambiguous to score against (see TestOutput.error). Prefer
      // that explanation over a generic "no reasoning" dead end.
      return (
        test.test_output?.goal_evaluation?.reason ||
        contractError ||
        endpointFailure?.message ||
        'No evaluation reasoning available'
      );
    }
    // On a failed call the target's response body *is* the response, and it is the only
    // place the actual reason appears (a safeguarding rejection, say). Falling straight to
    // "No response available" threw away the one thing the reader came for.
    return (
      test.test_output?.output ||
      endpointFailure?.responseBody ||
      endpointFailure?.message ||
      contractError ||
      'No response available'
    );
  }, [isMultiTurn, test, endpointFailure, contractError]);

  const checkGroups = useMemo(
    () =>
      buildResultChecks({
        metrics: test.test_metrics?.metrics,
        goalEvaluation: test.test_output?.goal_evaluation,
      }),
    [test]
  );
  const hasChecks = checkGroups.some(g => g.checks.length > 0);

  // Shown only when the run scored this test with its requirement's metrics.
  const checkedRequirement =
    (!metricsSource || metricsSource === MetricsSource.REQUIREMENT) &&
    checkGroups.some(g => g.key === 'metrics')
      ? test.test?.requirement
      : undefined;

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
      <StatusChip
        status={testStatus}
        label={testLabel}
        size="small"
        variant="filled"
      />
      {hasChecks && (
        <Typography variant="body1" color="text.secondary">
          {checksSummary(checkGroups)}
        </Typography>
      )}
      {hasChecks && onShowEvaluation && (
        <Link
          component="button"
          type="button"
          variant="body1"
          underline="hover"
          onClick={onShowEvaluation}
          sx={{ fontWeight: 500 }}
        >
          See Evaluation
        </Link>
      )}
      {test.last_annotation &&
        (hasConflictingAnnotation(test) ? (
          <Chip
            icon={<EditIcon sx={{ fontSize: 16 }} />}
            label="Corrected"
            size="small"
            color="warning"
            variant="filled"
            sx={{ fontWeight: 600 }}
          />
        ) : (
          <Chip
            icon={<CheckIcon sx={{ fontSize: 16 }} />}
            label="Confirmed"
            size="small"
            color="success"
            variant="filled"
            sx={{ fontWeight: 600 }}
          />
        ))}
    </Box>
  );

  // Explains an Error status that would otherwise be unexplained: the status chip alone
  // never said the target had rejected the call, let alone with which code.
  //
  // Gated on testStatus rather than on endpointFailure alone: getEffectiveTestResultStatus
  // is the single arbiter of a result's status (it projects the backend's execution/verdict
  // pair), so this only ever explains a status it decided. A result a reviewer has since
  // overridden to Pass must not still be topped by a failure banner.
  const endpointFailureBanner =
    endpointFailure && testStatus === 'Error' ? (
      <Alert
        severity="warning"
        icon={<ErrorOutlineIcon />}
        sx={{ mb: 3, borderRadius: BORDER_RADIUS.md }}
      >
        <AlertTitle>
          {endpointFailure.statusCode !== undefined
            ? `Target endpoint returned HTTP ${endpointFailure.statusCode}`
            : 'Target endpoint did not return a response'}
          {endpointFailure.reason ? ` (${endpointFailure.reason})` : ''}
        </AlertTitle>
        <Typography
          variant="body2"
          sx={{ mb: endpointFailure.message ? 1 : 0 }}
        >
          The test could not be scored, because the endpoint never produced an
          answer to evaluate.
        </Typography>
        {endpointFailure.message && (
          <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset' }}>
            {endpointFailure.message}
          </Box>
        )}
      </Alert>
    ) : null;

  // Shared card styling matching Figma "Data Output Textfield" card
  const cardSx = {
    p: 3,
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
        {endpointFailureBanner}

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
                  <Box
                    component="pre"
                    sx={{ ...testPreviewSx, minHeight: 'unset' }}
                  >
                    <JsonPreview value={test.test_output.metadata} />
                  </Box>
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
      {endpointFailureBanner}

      <Paper variant="outlined" sx={cardSx}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Typography variant="subtitle1" component="h3" fontWeight={600}>
            What&apos;s checked
          </Typography>

          <SectionField label="Goal">
            <Typography
              variant="body2"
              sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {promptContent}
            </Typography>
          </SectionField>

          {testConfig?.restrictions && (
            <SectionField label="Restrictions">
              {renderFormattedText(asSentenceList(testConfig.restrictions))}
            </SectionField>
          )}

          {checkedRequirement && (
            <>
              <Divider />
              <SectionField label={`Requirement: ${checkedRequirement.name}`}>
                <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                  {checkedRequirement.description || checkedRequirement.name}
                </Typography>
              </SectionField>
            </>
          )}
        </Box>
      </Paper>

      {(testConfig?.scenario || testConfig?.instructions) && (
        <Paper variant="outlined" sx={cardSx}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box>
              <Typography variant="subtitle1" component="h3" fontWeight={600}>
                Simulated user
              </Typography>
              <Typography variant="body2" color="text.secondary">
                How Penelope plays the user during the conversation.
              </Typography>
            </Box>

            {testConfig?.scenario && (
              <SectionField label="Scenario">
                {renderFormattedText(testConfig.scenario)}
              </SectionField>
            )}

            {testConfig?.instructions && (
              <SectionField label="Instructions">
                {renderFormattedText(testConfig.instructions)}
              </SectionField>
            )}
          </Box>
        </Paper>
      )}

      <Box sx={{ mb: 3 }}>
        <TestResultTags testResult={test} onUpdate={onTestResultUpdate} />
      </Box>

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
