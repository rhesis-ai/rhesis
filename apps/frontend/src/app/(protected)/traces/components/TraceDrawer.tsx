'use client';

import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  Divider,
  Chip,
  Stack,
  Tabs,
  Tab,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import FolderIcon from '@mui/icons-material/Folder';
import ApiIcon from '@mui/icons-material/Api';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import BubbleChartIcon from '@mui/icons-material/BubbleChart';
import Link from 'next/link';
import SpanTreeView from './SpanTreeView';
import SpanGraphView from './SpanGraphView';
import SpanDetailsPanel from './SpanDetailsPanel';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TraceDetailResponse,
  SpanNode,
} from '@/utils/api-client/interfaces/telemetry';
import { formatDuration } from '@/utils/format-duration';

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  traceId: string | null;
  projectId: string;
  sessionToken: string;
}

export default function TraceDrawer({
  open,
  onClose,
  traceId,
  projectId,
  sessionToken,
}: TraceDrawerProps) {
  const [trace, setTrace] = useState<TraceDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<SpanNode | null>(null);
  const [viewTab, setViewTab] = useState<number>(0);

  useEffect(() => {
    if (open && traceId && projectId) {
      fetchTrace();
    }
  }, [open, traceId, projectId]);

  // Add keyboard shortcut for ESC key
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const fetchTrace = async () => {
    if (!traceId || !projectId) return;

    setLoading(true);
    setError(null);
    setTrace(null);
    setSelectedSpan(null);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getTelemetryClient();
      const data = await client.getTrace(traceId, projectId);
      setTrace(data);

      // Auto-select root span
      if (data.root_spans.length > 0) {
        setSelectedSpan(data.root_spans[0]);
      }
    } catch (err: any) {
      const errorMsg = err.message || 'Failed to fetch trace details';
      setError(errorMsg);
      console.error('Failed to fetch trace:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSpanSelect = (span: SpanNode) => {
    setSelectedSpan(span);
  };

  const drawerContent = () => {
    if (loading) {
      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            p: 4,
          }}
        >
          <CircularProgress />
        </Box>
      );
    }

    if (error) {
      return (
        <Box sx={{ p: 3 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      );
    }

    if (!trace || !trace.root_spans || trace.root_spans.length === 0) {
      return (
        <Box sx={{ p: 3 }}>
          <Typography color="text.secondary">
            No trace data available
          </Typography>
        </Box>
      );
    }

    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            gap: 1,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography variant="h6">Trace Details</Typography>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Context Information */}
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              alignItems: 'center',
            }}
          >
            {/* Project */}
            {trace.project && (
              <Chip
                icon={<FolderIcon />}
                label={`Project: ${trace.project.name}`}
                component={Link}
                href={`/projects/${trace.project.id}`}
                target="_blank"
                clickable
                size="small"
                variant="outlined"
              />
            )}

            {/* Endpoint (if available) */}
            {trace.endpoint && (
              <Chip
                icon={<ApiIcon />}
                label={`Endpoint: ${trace.endpoint.name}`}
                component={Link}
                href={`/endpoints/${trace.endpoint.id}`}
                target="_blank"
                clickable
                size="small"
                variant="outlined"
              />
            )}

            {/* Test Run (if from test execution) */}
            {trace.test_run && (
              <Chip
                icon={<PlayArrowIcon />}
                label={`Test Run: ${trace.test_run.name || trace.test_run.nano_id || trace.test_run.id}`}
                component={Link}
                href={`/test-runs/${trace.test_run.id}`}
                target="_blank"
                clickable
                size="small"
                variant="outlined"
              />
            )}

            {/* Test (if from test execution) */}
            {trace.test && (
              <Chip
                icon={<AssignmentIcon />}
                label={`Test: ${trace.test.nano_id || trace.test.id}`}
                component={Link}
                href={`/tests/${trace.test.id}`}
                target="_blank"
                clickable
                size="small"
                variant="outlined"
              />
            )}
          </Box>

          {/* Trace Metrics */}
          <Stack direction="row" spacing={1}>
            <Chip
              label={`${trace.span_count} spans`}
              size="small"
              variant="outlined"
            />
            <Chip
              label={formatDuration(trace.duration_ms)}
              size="small"
              variant="outlined"
            />
            <Chip
              label={trace.environment}
              size="small"
              variant="outlined"
              color="default"
            />
            {trace.error_count > 0 && (
              <Chip
                label={`${trace.error_count} errors`}
                size="small"
                color="error"
                variant="outlined"
              />
            )}
            {trace.total_cost_usd > 0 && (
              <Chip
                label={`$${trace.total_cost_usd.toFixed(4)}`}
                size="small"
                variant="outlined"
              />
            )}
          </Stack>
        </Box>

        {/* Content - Split Layout */}
        <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Left: Span Tree */}
          <Box
            sx={{
              width: '40%',
              borderRight: 1,
              borderColor: 'divider',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
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
                value={viewTab}
                onChange={(_, newValue) => setViewTab(newValue)}
                aria-label="span hierarchy tabs"
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
                  icon={<AccountTreeIcon fontSize="small" />}
                  iconPosition="start"
                  label="Tree View"
                  id="span-hierarchy-tab-0"
                  aria-controls="span-hierarchy-tabpanel-0"
                />
                <Tab
                  icon={<BubbleChartIcon fontSize="small" />}
                  iconPosition="start"
                  label="Graph View"
                  id="span-hierarchy-tab-1"
                  aria-controls="span-hierarchy-tabpanel-1"
                />
              </Tabs>
            </Box>

            {/* Tab Content */}
            <Box
              sx={{
                flex: 1,
                overflow: viewTab === 1 ? 'hidden' : 'auto',
                p: viewTab === 1 ? 0 : theme => theme.spacing(2),
              }}
            >
              {viewTab === 0 && (
                <SpanTreeView
                  spans={trace.root_spans}
                  selectedSpan={selectedSpan}
                  onSpanSelect={handleSpanSelect}
                />
              )}
              {viewTab === 1 && (
                <SpanGraphView
                  spans={trace.root_spans}
                  selectedSpan={selectedSpan}
                  onSpanSelect={handleSpanSelect}
                />
              )}
            </Box>
          </Box>

          {/* Right: Span Details */}
          <Box
            sx={{
              width: '60%',
              overflow: 'auto',
            }}
          >
            <SpanDetailsPanel
              span={selectedSpan}
              trace={trace}
              sessionToken={sessionToken}
            />
          </Box>
        </Box>
      </Box>
    );
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      width="80%"
      showHeader={false}
      closeButtonText="Close"
    >
      {drawerContent()}
    </BaseDrawer>
  );
}
