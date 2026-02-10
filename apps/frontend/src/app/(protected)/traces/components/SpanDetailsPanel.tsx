'use client';

/* eslint-disable react/no-array-index-key -- Trace attribute display */

import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Chip,
  Divider,
  Card,
  CardContent,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableRow,
  TableCell,
  Tabs,
  Tab,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import {
  SpanNode,
  TraceDetailResponse,
} from '@/utils/api-client/interfaces/telemetry';
import { format } from 'date-fns';
import { formatDuration } from '@/utils/format-duration';
import TestResultTab from './TestResultTab';

interface SpanDetailsPanelProps {
  span: SpanNode | null;
  trace: TraceDetailResponse | null;
  sessionToken: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`span-detail-tabpanel-${index}`}
      aria-labelledby={`span-detail-tab-${index}`}
      style={{ height: '100%' }}
    >
      {value === index && <Box sx={{ height: '100%' }}>{children}</Box>}
    </div>
  );
}

export default function SpanDetailsPanel({
  span,
  trace,
  sessionToken,
}: SpanDetailsPanelProps) {
  const [activeTab, setActiveTab] = useState(0);

  // Determine if Test Result tab should be shown
  const showTestResultTab = trace?.test_result != null;

  // Reset activeTab to 0 when Test Result tab becomes unavailable
  useEffect(() => {
    if (!showTestResultTab && activeTab === 1) {
      setActiveTab(0);
    }
  }, [showTestResultTab, activeTab]);

  if (!span) {
    return (
      <Box sx={{ p: theme => theme.spacing(3) }}>
        <Typography color="text.secondary">
          Select a span to view details
        </Typography>
      </Box>
    );
  }

  // Categorize attributes
  const llmAttributes: Record<string, any> = {};
  const functionAttributes: Record<string, any> = {};
  const testAttributes: Record<string, any> = {};
  const otherAttributes: Record<string, any> = {};

  Object.entries(span.attributes).forEach(([key, value]) => {
    if (key.startsWith('ai.') || key.startsWith('llm.')) {
      llmAttributes[key] = value;
    } else if (key.startsWith('function.')) {
      functionAttributes[key] = value;
    } else if (key.startsWith('rhesis.test.')) {
      testAttributes[key] = value;
    } else {
      otherAttributes[key] = value;
    }
  });

  // Extract I/O attributes for prominent display
  const inputArgs = functionAttributes['function.args'];
  const inputKwargs = functionAttributes['function.kwargs'];
  const outputResult =
    functionAttributes['function.result'] ||
    functionAttributes['function.result_preview'];

  // Parse JSON if needed
  const parseIfJSON = (value: any) => {
    if (
      typeof value === 'string' &&
      (value.startsWith('[') || value.startsWith('{'))
    ) {
      try {
        return JSON.parse(value);
      } catch {
        return value;
      }
    }
    return value;
  };

  const parsedArgs = inputArgs ? parseIfJSON(inputArgs) : null;
  const parsedKwargs = inputKwargs ? parseIfJSON(inputKwargs) : null;
  const parsedOutput = outputResult ? parseIfJSON(outputResult) : null;

  // Remove I/O from function attributes (displayed separately)
  const {
    'function.args': _,
    'function.kwargs': __,
    'function.result': ___,
    'function.result_preview': ____,
    ...otherFunctionAttributes
  } = functionAttributes;

  // Extract LLM input/output from events (ai.prompt and ai.completion)
  const llmPromptEvents = span.events?.filter(
    (e: any) => e.name === 'ai.prompt'
  );
  const llmCompletionEvent = span.events?.find(
    (e: any) => e.name === 'ai.completion'
  );

  // Build LLM input from prompt events (can have multiple messages)
  const llmInput =
    llmPromptEvents && llmPromptEvents.length > 0
      ? llmPromptEvents.map((e: any) => ({
          role: e.attributes?.['ai.prompt.role'],
          content: e.attributes?.['ai.prompt.content'],
        }))
      : null;
  const llmOutput =
    llmCompletionEvent?.attributes?.['ai.completion.content'] || null;

  const parsedLlmInput = llmInput;
  const parsedLlmOutput = llmOutput ? parseIfJSON(llmOutput) : null;

  // Extract tool input/output from events (ai.tool.input and ai.tool.output)
  const toolInputEvent = span.events?.find(
    (e: any) => e.name === 'ai.tool.input'
  );
  const toolOutputEvent = span.events?.find(
    (e: any) => e.name === 'ai.tool.output'
  );

  const toolInput = toolInputEvent?.attributes?.['ai.tool.input'] || null;
  const toolOutput = toolOutputEvent?.attributes?.['ai.tool.output'] || null;

  const parsedToolInput = toolInput ? parseIfJSON(toolInput) : null;
  const parsedToolOutput = toolOutput ? parseIfJSON(toolOutput) : null;

  // Extract agent input/output from attributes
  const agentInputAttr = llmAttributes['ai.agent.input'];
  const agentOutputAttr = llmAttributes['ai.agent.output'];

  // Extract agent input/output from events
  const agentInputEvent = span.events?.find(
    (e: any) => e.name === 'ai.agent.input'
  );
  const agentOutputEvent = span.events?.find(
    (e: any) => e.name === 'ai.agent.output'
  );

  // Get agent input/output values (prefer attributes, fallback to events)
  const agentInput =
    agentInputAttr || agentInputEvent?.attributes?.['ai.agent.input'] || null;
  const agentOutput =
    agentOutputAttr ||
    agentOutputEvent?.attributes?.['ai.agent.output'] ||
    null;

  const parsedAgentInput = agentInput ? parseIfJSON(agentInput) : null;
  const parsedAgentOutput = agentOutput ? parseIfJSON(agentOutput) : null;

  // Filter out agent I/O from LLM attributes (displayed separately)
  const {
    'ai.agent.input': _____,
    'ai.agent.output': ______,
    ...otherLlmAttributes
  } = llmAttributes;

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tabs Header */}
      <Box
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          px: theme => theme.spacing(2),
          pt: theme => theme.spacing(2),
          pb: theme => theme.spacing(2),
          mb: theme => theme.spacing(1),
        }}
      >
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
          aria-label="span detail tabs"
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 'auto',
            '& .MuiTab-root': {
              minHeight: 'auto',
              fontSize: theme => theme.typography.subtitle2.fontSize,
              fontWeight: theme => theme.typography.subtitle2.fontWeight,
              textTransform: 'none',
              py: theme => theme.spacing(1.25),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              backgroundColor: 'transparent !important',
              color: theme => theme.palette.text.secondary,
              '& .MuiSvgIcon-root': {
                color: 'inherit',
              },
              '&.Mui-selected': {
                backgroundColor: 'transparent !important',
                color: theme => theme.palette.text.primary,
                '& .MuiSvgIcon-root': {
                  color: theme => theme.palette.text.primary,
                },
              },
              '&:hover': {
                backgroundColor: 'transparent !important',
              },
            },
            '& .MuiTabs-indicator': {
              display: 'none',
            },
            '& .MuiTabs-flexContainer': {
              backgroundColor: 'transparent',
            },
          }}
        >
          <Tab
            icon={<InfoOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Span Details"
            id="span-detail-tab-0"
            aria-controls="span-detail-tabpanel-0"
          />
          {showTestResultTab && (
            <Tab
              icon={<AssessmentOutlinedIcon fontSize="small" />}
              iconPosition="start"
              label="Test Results"
              id="span-detail-tab-1"
              aria-controls="span-detail-tabpanel-1"
            />
          )}
        </Tabs>
      </Box>

      {/* Tab Content */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {/* Span Details Tab */}
        <TabPanel value={activeTab} index={0}>
          <Box sx={{ p: theme => theme.spacing(2) }}>
            {/* Overview Card */}
            <Card
              variant="outlined"
              sx={{
                mb: theme => theme.spacing(2),
                backgroundColor: theme => theme.palette.primary.main + '08', // Very light primary color
                borderColor: theme => theme.palette.primary.main + '20',
              }}
            >
              <CardContent>
                <Stack spacing={2}>
                  {/* Span Name */}
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Span Name
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{ fontFamily: 'monospace' }}
                    >
                      {span.span_name}
                    </Typography>
                  </Box>

                  {/* Span ID */}
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Span ID
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: theme => theme.typography.body2.fontSize,
                      }}
                    >
                      {span.span_id}
                    </Typography>
                  </Box>

                  {/* Timing */}
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Timing
                    </Typography>
                    <Stack direction="row" spacing={2} sx={{ mt: 0.5 }}>
                      <Chip
                        label={`Duration: ${formatDuration(span.duration_ms)}`}
                        size="small"
                        variant="outlined"
                      />
                      <Chip
                        label={span.span_kind}
                        size="small"
                        variant="outlined"
                      />
                    </Stack>
                    <Typography
                      variant="caption"
                      display="block"
                      sx={{ mt: 0.5 }}
                    >
                      Start: {format(new Date(span.start_time), 'PPpp')}
                    </Typography>
                    <Typography variant="caption" display="block">
                      End: {format(new Date(span.end_time), 'PPpp')}
                    </Typography>
                  </Box>

                  {/* Status */}
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Status
                    </Typography>
                    <Box sx={{ mt: 0.5 }}>
                      <Chip
                        label={span.status_code}
                        color={span.status_code === 'OK' ? 'success' : 'error'}
                        size="small"
                      />
                      {span.status_message && (
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                          {span.status_message}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                </Stack>
              </CardContent>
            </Card>

            {/* Function Input/Output Card - Featured prominently */}
            {(parsedArgs || parsedKwargs || parsedOutput) && (
              <Card
                variant="outlined"
                sx={{
                  mb: 2,
                  backgroundColor: theme => theme.palette.success.main + '08',
                  borderColor: theme => theme.palette.success.main + '30',
                  borderWidth: 2,
                }}
              >
                <CardContent>
                  {/* Inputs */}
                  {(parsedArgs || parsedKwargs) && (
                    <Box sx={{ mb: 2 }}>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Input
                      </Typography>
                      {parsedArgs && (
                        <Box sx={{ mb: 1 }}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mb: 0.5 }}
                          >
                            Arguments (positional):
                          </Typography>
                          <Box
                            component="pre"
                            sx={{
                              p: 1.5,
                              backgroundColor: theme =>
                                theme.palette.mode === 'dark'
                                  ? theme.palette.grey[800]
                                  : theme.palette.grey[100],
                              borderRadius: theme => theme.shape.borderRadius,
                              overflow: 'auto',
                              fontSize: theme =>
                                theme.typography.body2.fontSize,
                              fontFamily: 'monospace',
                              margin: 0,
                              maxHeight: 200,
                            }}
                          >
                            {typeof parsedArgs === 'string'
                              ? parsedArgs
                              : JSON.stringify(parsedArgs, null, 2)}
                          </Box>
                        </Box>
                      )}
                      {parsedKwargs && (
                        <Box>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mb: 0.5 }}
                          >
                            Keyword arguments:
                          </Typography>
                          <Box
                            component="pre"
                            sx={{
                              p: 1.5,
                              backgroundColor: theme =>
                                theme.palette.mode === 'dark'
                                  ? theme.palette.grey[800]
                                  : theme.palette.grey[100],
                              borderRadius: theme => theme.shape.borderRadius,
                              overflow: 'auto',
                              fontSize: theme =>
                                theme.typography.body2.fontSize,
                              fontFamily: 'monospace',
                              margin: 0,
                              maxHeight: 200,
                            }}
                          >
                            {typeof parsedKwargs === 'string'
                              ? parsedKwargs
                              : JSON.stringify(parsedKwargs, null, 2)}
                          </Box>
                        </Box>
                      )}
                    </Box>
                  )}

                  {(parsedArgs || parsedKwargs) && parsedOutput && (
                    <Divider sx={{ my: 2 }} />
                  )}

                  {/* Output */}
                  {parsedOutput && (
                    <Box>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Output
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 300,
                        }}
                      >
                        {typeof parsedOutput === 'string'
                          ? parsedOutput
                          : JSON.stringify(parsedOutput, null, 2)}
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}

            {/* LLM Input/Output Card - For ai.llm.invoke spans */}
            {(parsedLlmInput || parsedLlmOutput) && (
              <Card
                variant="outlined"
                sx={{
                  mb: 2,
                  backgroundColor: theme => theme.palette.primary.main + '08',
                  borderColor: theme => theme.palette.primary.main + '30',
                  borderWidth: 2,
                }}
              >
                <CardContent>
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 2, fontWeight: 'medium' }}
                  >
                    LLM
                  </Typography>

                  {/* LLM Input (Prompt Messages) */}
                  {parsedLlmInput && parsedLlmInput.length > 0 && (
                    <Box sx={{ mb: parsedLlmOutput ? 2 : 0 }}>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Input
                      </Typography>
                      <Stack spacing={1}>
                        {parsedLlmInput.map((msg: any, idx: number) => (
                          <Box
                            key={idx}
                            sx={{
                              p: 1.5,
                              backgroundColor: theme =>
                                theme.palette.mode === 'dark'
                                  ? theme.palette.grey[800]
                                  : theme.palette.grey[100],
                              borderRadius: theme =>
                                `${theme.shape.borderRadius}px`,
                              borderLeft: theme =>
                                `3px solid ${
                                  msg.role === 'system'
                                    ? theme.palette.warning.main
                                    : msg.role === 'user'
                                      ? theme.palette.primary.main
                                      : theme.palette.success.main
                                }`,
                            }}
                          >
                            <Typography
                              variant="caption"
                              sx={{
                                fontWeight: 'bold',
                                textTransform: 'uppercase',
                                color: theme =>
                                  msg.role === 'system'
                                    ? theme.palette.warning.main
                                    : msg.role === 'user'
                                      ? theme.palette.primary.main
                                      : theme.palette.success.main,
                              }}
                            >
                              {msg.role || 'unknown'}
                            </Typography>
                            <Box
                              component="pre"
                              sx={{
                                mt: 0.5,
                                fontSize: theme =>
                                  theme.typography.body2.fontSize,
                                fontFamily: 'monospace',
                                margin: 0,
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                              }}
                            >
                              {typeof msg.content === 'string'
                                ? msg.content
                                : JSON.stringify(msg.content, null, 2)}
                            </Box>
                          </Box>
                        ))}
                      </Stack>
                    </Box>
                  )}

                  {parsedLlmInput && parsedLlmOutput && (
                    <Divider sx={{ my: 2 }} />
                  )}

                  {/* LLM Output (Completion) */}
                  {parsedLlmOutput && (
                    <Box>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Output
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 300,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {typeof parsedLlmOutput === 'string'
                          ? parsedLlmOutput
                          : JSON.stringify(parsedLlmOutput, null, 2)}
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Tool Input/Output Card - For ai.tool.invoke spans */}
            {(parsedToolInput || parsedToolOutput) && (
              <Card
                variant="outlined"
                sx={{
                  mb: 2,
                  backgroundColor: theme => theme.palette.warning.main + '08',
                  borderColor: theme => theme.palette.warning.main + '30',
                  borderWidth: 2,
                }}
              >
                <CardContent>
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 2, fontWeight: 'medium' }}
                  >
                    Tool
                  </Typography>

                  {/* Tool Input */}
                  {parsedToolInput && (
                    <Box sx={{ mb: parsedToolOutput ? 2 : 0 }}>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Input
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 200,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {typeof parsedToolInput === 'string'
                          ? parsedToolInput
                          : JSON.stringify(parsedToolInput, null, 2)}
                      </Box>
                    </Box>
                  )}

                  {parsedToolInput && parsedToolOutput && (
                    <Divider sx={{ my: 2 }} />
                  )}

                  {/* Tool Output */}
                  {parsedToolOutput && (
                    <Box>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Output
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 300,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {typeof parsedToolOutput === 'string'
                          ? parsedToolOutput
                          : JSON.stringify(parsedToolOutput, null, 2)}
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Agent Input/Output Card - For agent spans */}
            {(parsedAgentInput || parsedAgentOutput) && (
              <Card
                variant="outlined"
                sx={{
                  mb: 2,
                  backgroundColor: theme => theme.palette.info.main + '08',
                  borderColor: theme => theme.palette.info.main + '30',
                  borderWidth: 2,
                }}
              >
                <CardContent>
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 2, fontWeight: 'medium' }}
                  >
                    Agent
                  </Typography>

                  {/* Agent Input */}
                  {parsedAgentInput && (
                    <Box sx={{ mb: parsedAgentOutput ? 2 : 0 }}>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Input
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 200,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {typeof parsedAgentInput === 'string'
                          ? parsedAgentInput
                          : JSON.stringify(parsedAgentInput, null, 2)}
                      </Box>
                    </Box>
                  )}

                  {parsedAgentInput && parsedAgentOutput && (
                    <Divider sx={{ my: 2 }} />
                  )}

                  {/* Agent Output */}
                  {parsedAgentOutput && (
                    <Box>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 1 }}
                      >
                        Output
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          p: 1.5,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? theme.palette.grey[800]
                              : theme.palette.grey[100],
                          borderRadius: theme => theme.shape.borderRadius,
                          overflow: 'auto',
                          fontSize: theme => theme.typography.body2.fontSize,
                          fontFamily: 'monospace',
                          margin: 0,
                          maxHeight: 300,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {typeof parsedAgentOutput === 'string'
                          ? parsedAgentOutput
                          : JSON.stringify(parsedAgentOutput, null, 2)}
                      </Box>
                    </Box>
                  )}
                </CardContent>
              </Card>
            )}

            {/* LLM Attributes */}
            {Object.keys(otherLlmAttributes).length > 0 && (
              <Accordion
                defaultExpanded
                sx={{
                  backgroundColor: theme => theme.palette.info.main + '08', // Very light info color
                  borderColor: theme => theme.palette.info.main + '20',
                  mb: 1,
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    LLM Attributes ({Object.keys(otherLlmAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={otherLlmAttributes} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Function Attributes - Metadata only (I/O shown above) */}
            {Object.keys(otherFunctionAttributes).length > 0 && (
              <Accordion
                defaultExpanded
                sx={{
                  backgroundColor: theme => theme.palette.success.main + '08', // Very light success color
                  borderColor: theme => theme.palette.success.main + '20',
                  mb: 1,
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    Function Metadata (
                    {Object.keys(otherFunctionAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={otherFunctionAttributes} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Test Attributes */}
            {Object.keys(testAttributes).length > 0 && (
              <Accordion
                defaultExpanded
                sx={{
                  backgroundColor: theme => theme.palette.warning.main + '08', // Very light warning color
                  borderColor: theme => theme.palette.warning.main + '20',
                  mb: 1,
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    Test Attributes ({Object.keys(testAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={testAttributes} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Other Attributes */}
            {Object.keys(otherAttributes).length > 0 && (
              <Accordion
                sx={{
                  backgroundColor: theme => theme.palette.grey[500] + '08', // Very light grey color
                  borderColor: theme => theme.palette.grey[500] + '20',
                  mb: 1,
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    Other Attributes ({Object.keys(otherAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={otherAttributes} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Events */}
            {span.events && span.events.length > 0 && (
              <Accordion
                sx={{
                  backgroundColor: theme => theme.palette.secondary.main + '08', // Very light secondary color
                  borderColor: theme => theme.palette.secondary.main + '20',
                  mb: 1,
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    Events ({span.events.length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                    {span.events.map((event, idx) => (
                      <Card
                        key={idx}
                        variant="outlined"
                        sx={{
                          mb: 1,
                          backgroundColor: theme =>
                            theme.palette.background.paper,
                        }}
                      >
                        <CardContent>
                          <Box
                            component="pre"
                            sx={{
                              fontSize: theme =>
                                theme.typography.caption.fontSize,
                              overflow: 'auto',
                              margin: 0,
                            }}
                          >
                            {JSON.stringify(event, null, 2)}
                          </Box>
                        </CardContent>
                      </Card>
                    ))}
                  </Box>
                </AccordionDetails>
              </Accordion>
            )}
          </Box>
        </TabPanel>

        {/* Test Result Tab */}
        {showTestResultTab && (
          <TabPanel value={activeTab} index={1}>
            <TestResultTab trace={trace} sessionToken={sessionToken} />
          </TabPanel>
        )}
      </Box>
    </Box>
  );
}

function AttributesTable({ attributes }: { attributes: Record<string, any> }) {
  return (
    <Table size="small">
      <TableBody>
        {Object.entries(attributes).map(([key, value]) => (
          <TableRow key={key}>
            <TableCell
              sx={{
                fontFamily: 'monospace',
                fontSize: theme => theme.typography.body2.fontSize,
                width: '40%',
              }}
            >
              {key}
            </TableCell>
            <TableCell
              sx={{
                fontFamily: 'monospace',
                fontSize: theme => theme.typography.body2.fontSize,
                wordBreak: 'break-word',
              }}
            >
              {typeof value === 'object'
                ? JSON.stringify(value)
                : String(value)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
