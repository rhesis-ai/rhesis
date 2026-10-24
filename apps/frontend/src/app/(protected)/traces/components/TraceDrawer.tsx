'use client';

import { useTraceAnnotationTargets } from '@/components/annotations/useAnnotationTargets';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSession } from 'next-auth/react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { CloseIcon } from '@/components/icons';
import SpanTreeView from './SpanTreeView';
import SpanSequenceView from './SpanSequenceView';
import SpanGraphView from './SpanGraphView';
import SpanDetailsPanel from './SpanDetailsPanel';
import ConversationTraceView from './ConversationTraceView';
import TraceAnnotationDrawer from './TraceAnnotationDrawer';
import TraceDrawerHeader, {
  type TraceExperimentInfo,
} from './TraceDrawerHeader';
import { findSpanPath, pickInitialSelection, treeTabIndex } from './span-path';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TraceDetailResponse,
  TraceMetricsStatus,
  SpanNode,
} from '@/utils/api-client/interfaces/telemetry';
import { toMentionId } from '@/components/common/MentionTextInput';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type { TurnTraceTarget } from '@/utils/conversation-from-spans';
import {
  conversationTraceQuery,
  loadConversationTurns,
  type ConversationTurns,
} from '@/utils/conversation-traces';

interface TraceDrawerProps {
  open: boolean;
  onClose: () => void;
  traceId: string | null;
  projectId: string;
  initialTurnIndex?: number;
  /** OTel span_id to select on open; takes precedence over initialTurnIndex. */
  initialSpanId?: string;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  onTraceUpdated?: () => void;
}

export default function TraceDrawer({
  open,
  onClose,
  traceId,
  projectId,
  initialTurnIndex,
  initialSpanId,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  onTraceUpdated,
}: TraceDrawerProps) {
  const { status } = useSession();
  const [trace, setTrace] = useState<TraceDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [experimentInfo, setExperimentInfo] =
    useState<TraceExperimentInfo | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<SpanNode | null>(null);
  const [viewTab, setViewTab] = useState<number>(0);
  // The toolbar slot a view renders its own actions into (the Conversation view's create-test button).
  const [viewActions, setViewActions] = useState<HTMLElement | null>(null);

  // A turn reached from inside the drawer, valid only for the trace the parent opened.
  const [turnNav, setTurnNav] = useState<{
    openedOn: string | null;
    target: TurnTraceTarget;
  } | null>(null);
  const turnTarget = turnNav?.openedOn === traceId ? turnNav.target : null;
  const loadedTraceId = turnTarget?.traceId ?? traceId;
  const loadedProjectId = turnTarget?.projectId ?? projectId;

  const [conversation, setConversation] = useState<{
    key: string;
    turns: ConversationTurns;
  } | null>(null);

  // Resizable drawer width state
  const [drawerWidth, setDrawerWidth] = useState(85); // viewport percentage
  const [isResizingDrawer, setIsResizingDrawer] = useState(false);

  // Tab index computation for optional conversation tab
  const showConversationTab = !!trace?.conversation_id;
  const isConversationTrace = showConversationTab;
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
  const [leftPanelWidth, setLeftPanelWidth] = useState(46); // percentage
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // A refresh can still be in flight when the reader moves to another turn; only the latest
  // getTrace may update the drawer.
  const traceRequestRef = useRef(0);

  const fetchTrace = useCallback(async () => {
    if (!loadedTraceId || !loadedProjectId) return;

    const requestId = ++traceRequestRef.current;
    setLoading(true);
    setError(null);
    setTrace(null);
    setSelectedSpan(null);

    try {
      const clientFactory = new ApiClientFactory(undefined, loadedProjectId);
      const client = clientFactory.getTelemetryClient();
      const data = await client.getTrace(loadedTraceId, loadedProjectId);
      if (requestId !== traceRequestRef.current) return;
      setTrace(data);

      const { span, openTree } = pickInitialSelection(
        data,
        turnTarget
          ? { initialTurnIndex: turnTarget.rootIndex }
          : { initialSpanId, initialTurnIndex }
      );
      setSelectedSpan(span);
      // Moving between turns keeps the tab the reader is on.
      if (openTree && !turnTarget) {
        setViewTab(treeTabIndex(!!data.conversation_id));
      }
    } catch (err: unknown) {
      if (requestId !== traceRequestRef.current) return;
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to fetch trace details';
      setError(errorMsg);
      console.error('Failed to fetch trace:', err);
    } finally {
      if (requestId === traceRequestRef.current) setLoading(false);
    }
  }, [
    loadedTraceId,
    loadedProjectId,
    turnTarget,
    initialTurnIndex,
    initialSpanId,
  ]);

  const refreshTrace = useCallback(async () => {
    if (!loadedTraceId || !loadedProjectId) return;

    const requestId = ++traceRequestRef.current;
    try {
      const clientFactory = new ApiClientFactory(undefined, loadedProjectId);
      const client = clientFactory.getTelemetryClient();
      const data = await client.getTrace(loadedTraceId, loadedProjectId);
      if (requestId !== traceRequestRef.current) return;
      setTrace(data);

      setSelectedSpan(prev => {
        if (!prev) return data.root_spans[0] ?? null;
        return (
          findSpanPath(data.root_spans, prev.span_id)?.at(-1) ??
          data.root_spans[0] ??
          null
        );
      });
    } catch (err) {
      console.error('Failed to refresh trace:', err);
    }
  }, [loadedTraceId, loadedProjectId]);

  const conversationQuery = useMemo(
    () => (trace ? conversationTraceQuery(trace) : null),
    [trace]
  );
  const conversationKey = conversationQuery
    ? JSON.stringify(conversationQuery)
    : null;
  // Kept while moving between turns: on traces stored before the backend linked them, turn 1
  // has no conversation_id of its own to look the conversation up by.
  const turns =
    conversation && (conversation.key === conversationKey || turnTarget)
      ? conversation.turns
      : null;

  // Loaded once per conversation, not again on every turn the reader moves to.
  useEffect(() => {
    if (!trace || !conversationQuery || !conversationKey) return;
    if (conversation?.key === conversationKey) return;

    let cancelled = false;
    const client = new ApiClientFactory(
      undefined,
      loadedProjectId
    ).getTelemetryClient();
    loadConversationTurns(client, conversationQuery, trace)
      .then(loaded => {
        if (!cancelled)
          setConversation({ key: conversationKey, turns: loaded });
      })
      .catch(err => console.error('Failed to load conversation turns:', err));
    return () => {
      cancelled = true;
    };
  }, [
    trace,
    conversationQuery,
    conversationKey,
    conversation?.key,
    loadedProjectId,
  ]);

  // Index into the conversation's turns of the turn holding the selected span.
  const turnIndex = useMemo(() => {
    if (!turns || !trace || !selectedSpan) return null;
    const root = findSpanPath(trace.root_spans, selectedSpan.span_id)?.[0];
    if (!root) return null;
    const rootIndex = trace.root_spans.indexOf(root);
    const index = turns.targets.findIndex(
      t => t.traceId === trace.trace_id && t.rootIndex === rootIndex
    );
    return index >= 0 ? index : null;
  }, [turns, trace, selectedSpan]);

  // The loaded trace's roots are taken from it, not the conversation's copy, so a refresh after
  // an annotation shows.
  const conversationSpans = useMemo(
    () =>
      turns?.targets.map(
        (t, i) =>
          (t.traceId === trace?.trace_id && trace.root_spans[t.rootIndex]) ||
          turns.spans[i]
      ),
    [turns, trace]
  );

  const goToTurn = useCallback(
    (index: number) => {
      const target = turns?.targets[index];
      if (!target || !trace) return;
      if (target.traceId === trace.trace_id) {
        setSelectedSpan(trace.root_spans[target.rootIndex] ?? null);
      } else {
        setTurnNav({ openedOn: traceId, target });
      }
    },
    [turns, trace, traceId]
  );

  // Annotation drawer state (lifted from SpanDetailsPanel for cross-panel access)
  const [annotationDrawerOpen, setAnnotationDrawerOpen] = useState(false);
  const [annotationInitialComment, setAnnotationInitialComment] = useState<
    string | undefined
  >();
  const [annotationInitialStatus, setAnnotationInitialStatus] = useState<
    'passed' | 'failed' | undefined
  >();

  const { metrics: mentionableMetrics, turns: mentionableTurns } =
    useTraceAnnotationTargets(selectedSpan, trace);

  const traceMetricsStatus = useMemo(() => {
    return (trace?.trace_metrics_status as TraceMetricsStatus) ?? null;
  }, [trace]);

  const selectedTurnNumber = useMemo(() => {
    if (!selectedSpan || !trace?.root_spans) return null;
    if (turns) {
      const isRoot = trace.root_spans.some(
        s => s.span_id === selectedSpan.span_id
      );
      return isRoot && turnIndex !== null ? turnIndex + 1 : null;
    }
    if (!trace.conversation_id) return null;
    const conversationSpans = trace.root_spans.filter(
      s =>
        s.attributes['rhesis.conversation.input'] ||
        s.attributes['rhesis.conversation.output']
    );
    const idx = conversationSpans.findIndex(
      s => s.span_id === selectedSpan.span_id
    );
    return idx >= 0 ? idx + 1 : null;
  }, [selectedSpan, trace, turns, turnIndex]);

  const handleAnnotateMetric = useCallback(
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
      setAnnotationInitialComment(`@[${metricName}](metric:${slug}) `);
      setAnnotationInitialStatus(isSuccessful ? 'failed' : 'passed');
      setAnnotationDrawerOpen(true);
    },
    [selectedSpan]
  );

  const handleAnnotateTrace = useCallback(() => {
    setAnnotationInitialComment(undefined);
    setAnnotationInitialStatus(undefined);
    setAnnotationDrawerOpen(true);
  }, []);

  const handleAnnotateTurn = useCallback(
    (turnNumber: number, turnPassed?: boolean) => {
      setAnnotationInitialComment(`@[Turn ${turnNumber}](turn:${turnNumber}) `);
      setAnnotationInitialStatus(
        turnPassed === undefined ? undefined : turnPassed ? 'failed' : 'passed'
      );
      setAnnotationDrawerOpen(true);
    },
    []
  );

  const handleAnnotationSave = useCallback(async () => {
    await refreshTrace();
    onTraceUpdated?.();
  }, [refreshTrace, onTraceUpdated]);

  useEffect(() => {
    if (open && loadedTraceId && loadedProjectId) {
      fetchTrace();
    }
  }, [open, loadedTraceId, loadedProjectId, fetchTrace]);

  // Reopening, or the parent opening another trace, starts from what the parent asks for.
  useEffect(() => {
    setTurnNav(null);
  }, [open, traceId]);

  // Fetch experiment info from test run attributes
  useEffect(() => {
    const fetchExperimentInfo = async () => {
      if (!trace?.test_run?.id || !isAuthenticated(status) || !projectId) {
        setExperimentInfo(null);
        return;
      }
      try {
        const clientFactory = new ApiClientFactory(undefined, projectId);
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
  }, [trace?.test_run?.id, projectId, status]);

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

  // Loading and error states still need a way out: the drawer has no footer.
  const bareCloseBar = (
    <Box
      sx={{
        flexShrink: 0,
        display: 'flex',
        justifyContent: 'flex-end',
        px: 1.5,
        py: 1,
      }}
    >
      <IconButton size="small" aria-label="Close trace" onClick={onClose}>
        <CloseIcon fontSize="small" />
      </IconButton>
    </Box>
  );

  const drawerContent = () => {
    if (loading) {
      return (
        <>
          {bareCloseBar}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              flex: 1,
              p: 4,
            }}
          >
            <CircularProgress />
          </Box>
        </>
      );
    }

    if (error) {
      return (
        <>
          {bareCloseBar}
          <Box sx={{ px: 3 }}>
            <Alert severity="error">{error}</Alert>
          </Box>
        </>
      );
    }

    if (!trace || !trace.root_spans || trace.root_spans.length === 0) {
      return (
        <>
          {bareCloseBar}
          <Box sx={{ px: 3 }}>
            <Typography color="text.secondary">
              No trace data available
            </Typography>
          </Box>
        </>
      );
    }

    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0,
        }}
      >
        <TraceDrawerHeader
          trace={trace}
          experiment={experimentInfo}
          turnIndex={turnIndex}
          turnCount={turns?.targets.length ?? 0}
          onTurnChange={goToTurn}
          onClose={onClose}
        />

        <Box
          ref={containerRef}
          sx={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            overflow: 'hidden',
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
            <Box
              sx={{
                flexShrink: 0,
                minHeight: theme => theme.spacing(5.5),
                display: 'flex',
                alignItems: 'center',
                px: 2,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <ToggleButtonGroup
                value={activeViewKey}
                exclusive
                size="small"
                aria-label="Trace view"
                onChange={(_, key: string | null) => {
                  if (!key) return;
                  const index = viewTabs.findIndex(t => t.key === key);
                  if (index >= 0) setViewTab(index);
                }}
              >
                {viewTabs.map(tab => (
                  <ToggleButton
                    key={tab.key}
                    value={tab.key}
                    id={tab.id}
                    aria-controls={tab['aria-controls']}
                    sx={{ py: 0.25, px: 1.25, textTransform: 'none' }}
                  >
                    {tab.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
              <Box
                ref={setViewActions}
                sx={{ ml: 'auto', display: 'flex', alignItems: 'center' }}
              />
            </Box>

            <ErrorBoundary>
              <Box
                id={
                  viewTabs.find(t => t.key === activeViewKey)?.['aria-controls']
                }
                sx={{
                  flex: 1,
                  overflow:
                    activeViewKey === 'tree' || activeViewKey === 'conversation'
                      ? 'auto'
                      : 'hidden',
                  minHeight: 0,
                }}
              >
                {activeViewKey === 'conversation' && (
                  <ConversationTraceView
                    trace={trace}
                    onSpanSelect={handleSpanSelect}
                    rootSpans={conversationSpans ?? trace.root_spans}
                    onTurnClick={
                      turns ? turnNumber => goToTurn(turnNumber - 1) : undefined
                    }
                    onAnnotateTurn={handleAnnotateTurn}
                    selectedTurn={selectedTurnNumber}
                    actionsContainer={viewActions}
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
              isConversationTrace={isConversationTrace}
              currentUserId={currentUserId}
              currentUserName={currentUserName}
              currentUserPicture={currentUserPicture}
              onTraceUpdated={refreshTrace}
              onAnnotateMetric={handleAnnotateMetric}
              onAnnotateTrace={handleAnnotateTrace}
              onAnnotateTurn={handleAnnotateTurn}
              mentionableMetrics={mentionableMetrics}
              mentionableTurns={mentionableTurns}
              traceMetricsStatus={traceMetricsStatus}
              selectedTurnNumber={selectedTurnNumber}
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
      width={`${drawerWidth}%`}
      showHeader={false}
      closeButtonText=""
      contentLayout="fill"
      disablePadding
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
      <TraceAnnotationDrawer
        open={annotationDrawerOpen}
        onClose={() => {
          setAnnotationDrawerOpen(false);
          setAnnotationInitialComment(undefined);
          setAnnotationInitialStatus(undefined);
        }}
        selectedSpan={selectedSpan}
        onSave={handleAnnotationSave}
        initialComment={annotationInitialComment}
        initialStatus={annotationInitialStatus}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
      />
    </BaseDrawer>
  );
}
