'use client';

import { useState } from 'react';
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

            {/* LLM Attributes */}
            {Object.keys(llmAttributes).length > 0 && (
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
                    LLM Attributes ({Object.keys(llmAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={llmAttributes} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Function Attributes */}
            {Object.keys(functionAttributes).length > 0 && (
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
                    Function Attributes (
                    {Object.keys(functionAttributes).length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <AttributesTable attributes={functionAttributes} />
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
                          <pre
                            style={{
                              fontSize: '0.75rem', // caption fontSize
                              overflow: 'auto',
                              margin: 0,
                            }}
                          >
                            {JSON.stringify(event, null, 2)}
                          </pre>
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
