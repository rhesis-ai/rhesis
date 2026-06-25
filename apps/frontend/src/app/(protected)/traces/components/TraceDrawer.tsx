'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Box, Typography, CircularProgress, Alert, Paper } from '@mui/material';
import Link from 'next/link';
import SpanTreeView from './SpanTreeView';
import SpanSequenceView from './SpanSequenceView';
import SpanGraphView from './SpanGraphView';
import SpanDetailsPanel from './SpanDetailsPanel';
import ConversationTraceView from './ConversationTraceView';
import TraceReviewDrawer from './TraceReviewDrawer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import BaseDrawer from '@/components/common/BaseDrawer';
import DetailTabNav from '@/components/common/DetailTabNav';
import { GridBadge } from '@/components/common/GridBadge';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TraceDetailResponse,
  TraceMetricsStatus,
  SpanNode,
} from '@/utils/api-client/interfaces/telemetry';
import {
  MentionOption,
  toMentionId,
} from '@/components/common/MentionTextInput';
import { formatDuration } from '@/utils/format-duration';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import { experimentHref } from '@/utils/experiment-links';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  traceId: string | null;
  projectId: string;
  sessionToken: string;
  initialTurnIndex?: number;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  onTraceUpdated?: () => void;
}

function TraceMetadataRow({
  label,
  href,
  children,
}: {
  label: string;
  href?: string;
  children: React.ReactNode;
}) {
  const pillSx = {
    display: 'inline-flex',
    alignItems: 'center',
    px: '10px',
    py: '2px',
    borderRadius: BORDER_RADIUS.pill,
    border: '1px solid',
    borderColor: 'greyscale.border',
    fontSize: 12,
    lineHeight: '18px',
    color: 'greyscale.body',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
    ...(href
      ? {
          '&:hover': {
            borderColor: 'primary.main',
            color: 'primary.main',
          },
        }
      : {}),
  } as const;

  return (
    <Box sx={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
      <Typography
        sx={{
          fontSize: 12,
          lineHeight: '18px',
          color: 'greyscale.body',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>
      {href ? (
        <Box component={Link} href={href} target="_blank" sx={pillSx}>
          {children}
        </Box>
      ) : (
        <Box sx={pillSx}>{children}</Box>
      )}
    </Box>
  );
}

export default function TraceDrawer({
  open,
  onClose,
  traceId,
  projectId,
  sessionToken,
  initialTurnIndex,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  onTraceUpdated,
}: TraceDrawerProps) {
  const [trace, setTrace] = useState<TraceDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [experimentInfo, setExperimentInfo] = useState<{
    id: string;
    name: string;
    version: string;
  } | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<SpanNode | null>(null);
  const [viewTab, setViewTab] = useState<number>(0);

  // Resizable drawer width state
  const [drawerWidth, setDrawerWidth] = useState(85); // viewport percentage
  const [isResizingDrawer, setIsResizingDrawer] = useState(false);

  // Tab index computation for optional conversation tab
  const showConversationTab = !!trace?.conversation_id;
  const isConversationTrace = showConversationTab;
  const hasTraceMetrics =
    trace?.root_spans?.some(
      s => s.trace_metrics && Object.keys(s.trace_metrics).length > 0
    ) ?? false;

  const viewTabs = useMemo(() => {
    const tabs: {
      key: string;
      label: string;
      id: string;
      'aria-controls': string;
    }[] = [];
    if (showConversationTab) {
      tabs.push({
        key: 'conversation',
        label: 'Conversation',
        id: 'span-hierarchy-tab-conversation',
        'aria-controls': 'span-hierarchy-tabpanel-conversation',
      });
    }
    tabs.push(
      {
        key: 'tree',
        label: 'Tree',
        id: 'span-hierarchy-tab-tree',
        'aria-controls': 'span-hierarchy-tabpanel-tree',
      },
      {
        key: 'sequence',
        label: 'Sequence',
        id: 'span-hierarchy-tab-sequence',
        'aria-controls': 'span-hierarchy-tabpanel-sequence',
      },
      {
        key: 'graph',
        label: 'Graph',
        id: 'span-hierarchy-tab-graph',
        'aria-controls': 'span-hierarchy-tabpanel-graph',
      }
    );
    return tabs;
  }, [showConversationTab]);

  const activeViewKey = viewTabs[viewTab]?.key ?? 'tree';

  // Resizable split pane state
  const [leftPanelWidth, setLeftPanelWidth] = useState(60); // percentage
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchTrace = useCallback(async () => {
    if (!traceId || !projectId) return;

    setLoading(true);
    setError(null);
    setTrace(null);
    setSelectedSpan(null);

    try {
      const clientFactory = new ApiClientFactory(sessionToken, projectId);
      const client = clientFactory.getTelemetryClient();
      const data = await client.getTrace(traceId, projectId);
      setTrace(data);

      if (data.root_spans.length > 0) {
        const spanIndex =
          initialTurnIndex !== undefined
            ? Math.min(initialTurnIndex, data.root_spans.length - 1)
            : 0;
        setSelectedSpan(data.root_spans[spanIndex]);

        if (initialTurnIndex !== undefined) {
          setViewTab(data.conversation_id ? 1 : 0);
        }
      }
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to fetch trace details';
      setError(errorMsg);
      console.error('Failed to fetch trace:', err);
    } finally {
      setLoading(false);
    }
  }, [traceId, projectId, sessionToken, initialTurnIndex]);

  const refreshTrace = useCallback(async () => {
    if (!traceId || !projectId) return;

    try {
      const clientFactory = new ApiClientFactory(sessionToken, projectId);
      const client = clientFactory.getTelemetryClient();
      const data = await client.getTrace(traceId, projectId);
      setTrace(data);

      setSelectedSpan(prev => {
        if (!prev) return data.root_spans[0] ?? null;
        const findSpan = (spans: SpanNode[]): SpanNode | null => {
          for (const s of spans) {
            if (s.span_id === prev.span_id) return s;
            const found = findSpan(s.children);
            if (found) return found;
          }
          return null;
        };
        return findSpan(data.root_spans) ?? data.root_spans[0] ?? null;
      });
    } catch (err) {
      console.error('Failed to refresh trace:', err);
    }
  }, [traceId, projectId, sessionToken]);

  // Review drawer state (lifted from SpanDetailsPanel for cross-panel access)
  const [reviewDrawerOpen, setReviewDrawerOpen] = useState(false);
  const [reviewInitialComment, setReviewInitialComment] = useState<
    string | undefined
  >();
  const [reviewInitialStatus, setReviewInitialStatus] = useState<
    'passed' | 'failed' | undefined
  >();

  const mentionableMetrics: MentionOption[] = useMemo(() => {
    const traceMetrics = selectedSpan?.trace_metrics as
      | Record<string, unknown>
      | undefined;
    if (!traceMetrics) return [];
    const names: string[] = [];
    for (const section of ['turn_metrics', 'conversation_metrics']) {
      const sectionData = traceMetrics[section] as
        | Record<string, unknown>
        | undefined;
      const metrics = sectionData?.metrics as
        | Record<string, unknown>
        | undefined;
      if (metrics) {
        names.push(...Object.keys(metrics));
      }
    }
    return names.map(name => ({
      id: toMentionId(name),
      display: name,
      type: 'metric' as const,
    }));
  }, [selectedSpan]);

  const mentionableTurns: MentionOption[] = useMemo(() => {
    if (!trace?.root_spans || !trace.conversation_id) return [];
    return trace.root_spans
      .filter(
        span =>
          span.attributes['rhesis.conversation.input'] ||
          span.attributes['rhesis.conversation.output']
      )
      .map((_, i) => ({
        id: String(i + 1),
        display: `Turn ${i + 1}`,
        type: 'turn' as const,
      }));
  }, [trace]);

  const traceMetricsStatus = useMemo(() => {
    return (trace?.trace_metrics_status as TraceMetricsStatus) ?? null;
  }, [trace]);

  const selectedTurnNumber = useMemo(() => {
    if (!selectedSpan || !trace?.root_spans || !trace.conversation_id)
      return null;
    const conversationSpans = trace.root_spans.filter(
      s =>
        s.attributes['rhesis.conversation.input'] ||
        s.attributes['rhesis.conversation.output']
    );
    const idx = conversationSpans.findIndex(
      s => s.span_id === selectedSpan.span_id
    );
    return idx >= 0 ? idx + 1 : null;
  }, [selectedSpan, trace]);

  const handleReviewMetric = useCallback(
    (metricName: string) => {
      const traceMetrics = selectedSpan?.trace_metrics as
        | Record<string, unknown>
        | undefined;
      if (!traceMetrics) return;

      let isSuccessful = false;
      for (const section of ['turn_metrics', 'conversation_metrics']) {
        const sectionData = traceMetrics[section] as
          | Record<string, unknown>
          | undefined;
        const metrics = sectionData?.metrics as
          | Record<string, { is_successful?: boolean }>
          | undefined;
        if (metrics?.[metricName]) {
          isSuccessful = !!metrics[metricName].is_successful;
          break;
        }
      }

      const slug = toMentionId(metricName);
      setReviewInitialComment(`@[${metricName}](metric:${slug}) `);
      setReviewInitialStatus(isSuccessful ? 'failed' : 'passed');
      setReviewDrawerOpen(true);
    },
    [selectedSpan]
  );

  const handleReviewTrace = useCallback(() => {
    setReviewInitialComment(undefined);
    setReviewInitialStatus(undefined);
    setReviewDrawerOpen(true);
  }, []);

  const handleReviewTurn = useCallback(
    (turnNumber: number, turnSuccess: boolean) => {
      setReviewInitialComment(`@[Turn ${turnNumber}](turn:${turnNumber}) `);
      setReviewInitialStatus(turnSuccess ? 'failed' : 'passed');
      setReviewDrawerOpen(true);
    },
    []
  );

  const handleReviewSave = useCallback(async () => {
    await refreshTrace();
    onTraceUpdated?.();
  }, [refreshTrace, onTraceUpdated]);

  useEffect(() => {
    if (open && traceId && projectId) {
      fetchTrace();
    }
  }, [open, traceId, projectId, fetchTrace]);

  // Fetch experiment info from test run attributes
  useEffect(() => {
    const fetchExperimentInfo = async () => {
      if (!trace?.test_run?.id || !sessionToken || !projectId) {
        setExperimentInfo(null);
        return;
      }
      try {
        const clientFactory = new ApiClientFactory(sessionToken, projectId);
        const testRunsClient = clientFactory.getTestRunsClient();
        const testRun = await testRunsClient.getTestRun(trace.test_run.id);
        if (testRun?.experiment_id) {
          const attrs = testRun.attributes as
            | Record<string, unknown>
            | undefined;
          setExperimentInfo({
            id: testRun.experiment_id,
            name: (attrs?.parameter_experiment_name as string) || 'Unknown',
            version: (attrs?.parameter_version as string) || '',
          });
        } else {
          setExperimentInfo(null);
        }
      } catch {
        setExperimentInfo(null);
      }
    };
    fetchExperimentInfo();
  }, [trace?.test_run?.id, sessionToken, projectId]);

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

  const handleSpanSelect = (span: SpanNode) => {
    setSelectedSpan(span);
  };

  // Resizable split pane handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth =
        ((e.clientX - containerRect.left) / containerRect.width) * 100;

      // Clamp between 20% and 80%
      const clampedWidth = Math.min(Math.max(newWidth, 20), 80);
      setLeftPanelWidth(clampedWidth);
    },
    [isDragging]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Drawer resize handlers
  const handleDrawerResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingDrawer(true);
  }, []);

  const handleDrawerResizeMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizingDrawer) return;
      const newWidth =
        ((window.innerWidth - e.clientX) / window.innerWidth) * 100;
      setDrawerWidth(Math.min(Math.max(newWidth, 30), 95));
    },
    [isResizingDrawer]
  );

  const handleDrawerResizeEnd = useCallback(() => {
    setIsResizingDrawer(false);
  }, []);

  // Add/remove mouse event listeners for split pane dragging
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (!isResizingDrawer) {
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      }
    };
  }, [isDragging, handleMouseMove, handleMouseUp, isResizingDrawer]);

  // Add/remove mouse event listeners for drawer width resizing
  useEffect(() => {
    if (isResizingDrawer) {
      document.addEventListener('mousemove', handleDrawerResizeMove);
      document.addEventListener('mouseup', handleDrawerResizeEnd);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'ew-resize';
    }

    return () => {
      document.removeEventListener('mousemove', handleDrawerResizeMove);
      document.removeEventListener('mouseup', handleDrawerResizeEnd);
      if (!isDragging) {
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
      }
    };
  }, [
    isResizingDrawer,
    handleDrawerResizeMove,
    handleDrawerResizeEnd,
    isDragging,
  ]);

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
          gap: '40px',
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            flexShrink: 0,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '30px',
              alignItems: 'center',
            }}
          >
            {trace.project && (
              <TraceMetadataRow
                label="Project:"
                href={`/projects/${trace.project.id}`}
              >
                {trace.project.name}
              </TraceMetadataRow>
            )}
            {trace.endpoint && (
              <TraceMetadataRow
                label="Endpoint:"
                href={`/endpoints/${trace.endpoint.id}`}
              >
                {trace.endpoint.name}
              </TraceMetadataRow>
            )}
            {trace.test_run && (
              <TraceMetadataRow
                label="Test Run:"
                href={`/test-runs/${trace.test_run.id}`}
              >
                {trace.test_run.name ||
                  trace.test_run.nano_id ||
                  trace.test_run.id}
              </TraceMetadataRow>
            )}
            {trace.test && (
              <TraceMetadataRow label="Test:" href={`/tests/${trace.test.id}`}>
                {trace.test.nano_id || trace.test.id}
              </TraceMetadataRow>
            )}
            {experimentInfo && (
              <TraceMetadataRow
                label="Experiment:"
                href={experimentHref(experimentInfo.id, experimentInfo.version)}
              >
                {experimentInfo.name}
                {experimentInfo.version
                  ? ` (${shortVersion(experimentInfo.version)})`
                  : ''}
              </TraceMetadataRow>
            )}
          </Box>

          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            <GridBadge label={`${trace.span_count} spans`} size="grid" />
            <GridBadge label={formatDuration(trace.duration_ms)} size="grid" />
            <GridBadge label={trace.environment} size="grid" />
            {trace.error_count > 0 && (
              <GridBadge
                label={`${trace.error_count} errors`}
                size="grid"
                sx={{
                  bgcolor: 'error.main',
                  color: 'error.contrastText',
                }}
              />
            )}
          </Box>
        </Box>

        <Paper
          ref={containerRef}
          elevation={0}
          sx={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            overflow: 'hidden',
            borderRadius: BORDER_RADIUS.md,
            boxShadow: theme =>
              theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
            bgcolor: 'background.paper',
          }}
        >
          <Box
            sx={{
              width: `${leftPanelWidth}%`,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
            }}
          >
            <Box sx={{ flexShrink: 0, px: '30px', pt: '30px' }}>
              <DetailTabNav
                tabs={viewTabs}
                activeIndex={viewTab}
                onChange={setViewTab}
                aria-label="span hierarchy tabs"
                tabGap="20px"
                scrollable
              />
            </Box>

            <ErrorBoundary>
              <Box
                sx={{
                  flex: 1,
                  overflow:
                    activeViewKey === 'tree' || activeViewKey === 'conversation'
                      ? 'auto'
                      : 'hidden',
                  px: activeViewKey === 'tree' ? '30px' : 0,
                  pb: '30px',
                  minHeight: 0,
                }}
              >
                {activeViewKey === 'conversation' && (
                  <ConversationTraceView
                    trace={trace}
                    sessionToken={sessionToken}
                    onSpanSelect={handleSpanSelect}
                    rootSpans={trace.root_spans}
                    onReviewTurn={
                      hasTraceMetrics ? handleReviewTurn : undefined
                    }
                  />
                )}
                {activeViewKey === 'tree' && (
                  <SpanTreeView
                    spans={trace.root_spans}
                    selectedSpan={selectedSpan}
                    onSpanSelect={handleSpanSelect}
                    isConversationTrace={isConversationTrace}
                  />
                )}
                {activeViewKey === 'sequence' && (
                  <SpanSequenceView
                    spans={trace.root_spans}
                    selectedSpan={selectedSpan}
                    onSpanSelect={handleSpanSelect}
                    isConversationTrace={isConversationTrace}
                    rootSpans={trace.root_spans}
                  />
                )}
                {activeViewKey === 'graph' && (
                  <SpanGraphView
                    spans={trace.root_spans}
                    selectedSpan={selectedSpan}
                    onSpanSelect={handleSpanSelect}
                    isConversationTrace={isConversationTrace}
                    rootSpans={trace.root_spans}
                  />
                )}
              </Box>
            </ErrorBoundary>
          </Box>

          <Box
            onMouseDown={handleMouseDown}
            sx={{
              width: theme => theme.spacing(0.125),
              flexShrink: 0,
              backgroundColor: theme =>
                isDragging ? theme.palette.primary.main : theme.palette.divider,
              cursor: 'col-resize',
              transition: theme =>
                isDragging
                  ? 'none'
                  : theme.transitions.create('background-color'),
              position: 'relative',
              '&::before': {
                content: '""',
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: theme => theme.spacing(-0.5),
                right: theme => theme.spacing(-0.5),
              },
              '&:hover': {
                backgroundColor: theme => theme.palette.primary.main,
              },
            }}
          />

          <Box
            sx={{
              flex: 1,
              overflow: 'hidden',
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <SpanDetailsPanel
              span={selectedSpan}
              trace={trace}
              sessionToken={sessionToken}
              hasTraceMetrics={hasTraceMetrics}
              isConversationTrace={isConversationTrace}
              currentUserId={currentUserId}
              currentUserName={currentUserName}
              currentUserPicture={currentUserPicture}
              onTraceUpdated={refreshTrace}
              onReviewMetric={handleReviewMetric}
              onReviewTrace={handleReviewTrace}
              onReviewTurn={hasTraceMetrics ? handleReviewTurn : undefined}
              mentionableMetrics={mentionableMetrics}
              mentionableTurns={mentionableTurns}
              traceMetricsStatus={traceMetricsStatus}
              selectedTurnNumber={selectedTurnNumber}
            />
          </Box>
        </Paper>
      </Box>
    );
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      width={`${drawerWidth}%`}
      showHeader={false}
      closeButtonText="Close"
      contentLayout="fill"
    >
      <Box
        sx={{
          position: 'relative',
          height: '100%',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Drawer width resize handle */}
        <Box
          onMouseDown={handleDrawerResizeStart}
          sx={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: theme => theme.spacing(0.75),
            cursor: 'ew-resize',
            zIndex: 10,
            '&::after': {
              content: '""',
              position: 'absolute',
              left: 0,
              top: 0,
              bottom: 0,
              width: theme => theme.spacing(0.375),
              backgroundColor: theme =>
                isResizingDrawer ? theme.palette.primary.main : 'transparent',
              transition: theme =>
                isResizingDrawer
                  ? 'none'
                  : theme.transitions.create('background-color'),
            },
            '&:hover::after': {
              backgroundColor: theme => theme.palette.primary.main,
            },
          }}
        />
        {drawerContent()}
      </Box>
      {hasTraceMetrics && (
        <TraceReviewDrawer
          open={reviewDrawerOpen}
          onClose={() => {
            setReviewDrawerOpen(false);
            setReviewInitialComment(undefined);
            setReviewInitialStatus(undefined);
          }}
          selectedSpan={selectedSpan}
          sessionToken={sessionToken}
          onSave={handleReviewSave}
          initialComment={reviewInitialComment}
          initialStatus={reviewInitialStatus}
          mentionableMetrics={mentionableMetrics}
          mentionableTurns={mentionableTurns}
        />
      )}
    </BaseDrawer>
  );
}
