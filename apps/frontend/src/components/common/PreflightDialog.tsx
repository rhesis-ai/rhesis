'use client';

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Collapse,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  CircularProgress,
  Box,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import ReplayIcon from '@mui/icons-material/Replay';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useWebSocket } from '@/hooks/useWebSocket';
import {
  EventType,
  PreflightCheckUpdatePayload,
  PreflightCompletePayload,
  WebSocketMessage,
} from '@/utils/websocket/types';

const DEFAULT_DESCRIPTIONS: Record<string, string> = {
  test_set_not_empty: 'Checking the test set contains tests',
  endpoint_connectivity: 'Testing endpoint reachability',
  evaluation_model: 'Validating evaluation model configuration',
  execution_model: 'Validating execution model configuration',
  behavior_metric_coverage: 'Checking behavior-metric associations',
  metric_functionality: 'Verifying metric implementations',
};

interface CheckState {
  check_id: string;
  label: string;
  status: 'running' | 'passed' | 'failed' | 'warning' | 'skipped';
  message?: string;
  detail?: string;
  composite_key: string;
  test_set_id?: string;
  test_set_name?: string;
}

interface PreflightDialogProps {
  open: boolean;
  correlationId: string;
  initialChecks: Array<{
    check_id: string;
    label: string;
    applicable: boolean;
    test_set_id?: string;
    test_set_name?: string;
    composite_key?: string;
  }>;
  onStart?: () => void;
  onProceed: () => void;
  onCancel: () => void;
  onRetry: () => void;
}

export function PreflightDialog({
  open,
  correlationId,
  initialChecks,
  onStart,
  onProceed,
  onCancel,
  onRetry,
}: PreflightDialogProps) {
  const [checks, setChecks] = useState<Map<string, CheckState>>(new Map());
  const [summary, setSummary] = useState<PreflightCompletePayload | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!open) return;
    setChecks(new Map());
    setSummary(null);
    setExpanded(new Set());
    setTimedOut(false);
  }, [correlationId, open]);

  const channels = useMemo(
    () => (open ? [`preflight:${correlationId}`] : []),
    [open, correlationId]
  );

  const toCheckState = (p: PreflightCheckUpdatePayload): CheckState => {
    const key = p.composite_key || p.check_id;
    return {
      check_id: p.check_id,
      label: p.label,
      status: p.status,
      message: p.message,
      detail: p.detail,
      composite_key: key,
      test_set_id: p.test_set_id,
      test_set_name: p.test_set_name,
    };
  };

  const upsertChecks = useCallback(
    (items: PreflightCheckUpdatePayload[]) => {
      setChecks(prev => {
        const next = new Map(prev);
        for (const item of items) {
          const state = toCheckState(item);
          next.set(state.composite_key, state);
        }
        return next;
      });
    },
    []
  );

  const handleCheckUpdate = useCallback(
    (msg: WebSocketMessage) => {
      const payload = msg.payload as unknown as PreflightCheckUpdatePayload;
      if (!payload?.check_id) return;
      upsertChecks([payload]);
    },
    [upsertChecks]
  );

  const handleComplete = useCallback(
    (msg: WebSocketMessage) => {
      const payload = msg.payload as unknown as PreflightCompletePayload;
      if (!payload) return;
      if (payload.checks?.length) {
        upsertChecks(payload.checks);
      }
      setSummary(payload);
    },
    [upsertChecks]
  );

  const wsOptions = useMemo(
    () => ({
      channels,
      eventHandlers: {
        [EventType.PREFLIGHT_CHECK_UPDATE]: handleCheckUpdate,
        [EventType.PREFLIGHT_COMPLETE]: handleComplete,
      },
    }),
    [channels, handleCheckUpdate, handleComplete]
  );

  const { isConnected } = useWebSocket(wsOptions);

  const onStartCalledRef = useRef<string | null>(null);

  useEffect(() => {
    if (
      open &&
      isConnected &&
      onStart &&
      onStartCalledRef.current !== correlationId
    ) {
      onStartCalledRef.current = correlationId;
      onStart();
    }
  }, [open, isConnected, onStart, correlationId]);

  useEffect(() => {
    if (!open) {
      onStartCalledRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open || initialChecks.length === 0) return;
    setChecks(prev => {
      const next = new Map(prev);
      for (const c of initialChecks) {
        const key = c.composite_key || c.check_id;
        if (!next.has(key)) {
          next.set(key, toCheckState({
            check_id: c.check_id,
            label: c.label,
            status: c.applicable ? 'running' : 'skipped',
            message: c.applicable ? undefined : 'Not applicable',
            composite_key: key,
            test_set_id: c.test_set_id,
            test_set_name: c.test_set_name,
            correlation_id: correlationId,
          }));
        }
      }
      return next;
    });
  }, [open, initialChecks, correlationId]);

  useEffect(() => {
    if (!open || summary || timedOut) return;
    const timeout = Math.max(60_000, initialChecks.length * 10_000);
    const timer = setTimeout(() => setTimedOut(true), timeout);
    return () => clearTimeout(timer);
  }, [open, summary, timedOut, correlationId, initialChecks.length]);

  const isRunning = !summary && !timedOut;
  const allPassed = summary?.summary === 'passed';
  const hasErrors = summary !== null && summary.failed > 0;
  const hasWarningsOnly =
    summary !== null && summary.failed === 0 && summary.warnings > 0;

  const getStatusIcon = (status: CheckState['status']) => {
    switch (status) {
      case 'running':
        return <CircularProgress size={20} />;
      case 'passed':
        return <CheckCircleOutlineIcon color="success" />;
      case 'failed':
        return <ErrorOutlineIcon color="error" />;
      case 'warning':
        return <WarningAmberIcon color="warning" />;
      case 'skipped':
        return <SkipNextIcon color="disabled" />;
    }
  };

  const checkList = Array.from(checks.values());

  const isMultiTestSet = useMemo(() => {
    const ids = new Set(checkList.map(c => c.test_set_id).filter(Boolean));
    return ids.size > 1;
  }, [checkList]);

  const { sharedChecks, testSetGroups } = useMemo(() => {
    if (!isMultiTestSet) {
      return { sharedChecks: checkList, testSetGroups: [] as [string, CheckState[]][] };
    }

    const shared: CheckState[] = [];
    const byTestSet = new Map<string, CheckState[]>();

    for (const check of checkList) {
      if (!check.test_set_id) {
        shared.push(check);
      } else {
        const name = check.test_set_name || check.test_set_id;
        const group = byTestSet.get(name) || [];
        group.push(check);
        byTestSet.set(name, group);
      }
    }

    return {
      sharedChecks: shared,
      testSetGroups: Array.from(byTestSet.entries()),
    };
  }, [checkList, isMultiTestSet]);

  const hasDetail = (check: CheckState) => !!check.detail;

  const toggleExpanded = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renderCheckItem = (check: CheckState) => {
    const expandable = hasDetail(check);
    const isExpanded = expanded.has(check.composite_key);
    const secondaryText =
      check.message ||
      DEFAULT_DESCRIPTIONS[check.check_id] ||
      undefined;

    return (
      <React.Fragment key={check.composite_key}>
        {expandable ? (
          <ListItemButton
            onClick={() => toggleExpanded(check.composite_key)}
            sx={{ py: 0.5, borderRadius: 1 }}
          >
            <ListItemIcon sx={{ minWidth: theme => theme.spacing(4.5) }}>
              {getStatusIcon(check.status)}
            </ListItemIcon>
            <ListItemText
              primary={check.label}
              secondary={secondaryText}
              primaryTypographyProps={{ variant: 'body2' }}
              secondaryTypographyProps={{ variant: 'caption' }}
            />
            {isExpanded ? (
              <ExpandLessIcon fontSize="small" color="action" />
            ) : (
              <ExpandMoreIcon fontSize="small" color="action" />
            )}
          </ListItemButton>
        ) : (
          <ListItem sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: theme => theme.spacing(4.5) }}>
              {getStatusIcon(check.status)}
            </ListItemIcon>
            <ListItemText
              primary={check.label}
              secondary={secondaryText}
              primaryTypographyProps={{ variant: 'body2' }}
              secondaryTypographyProps={{ variant: 'caption' }}
            />
          </ListItem>
        )}
        {expandable && (
          <Collapse in={isExpanded}>
            <Box
              sx={{
                ml: 6.5,
                mr: 2,
                mb: 1,
                p: 1.5,
                bgcolor: 'action.hover',
                borderRadius: 1,
              }}
            >
              <Typography variant="caption" color="text.secondary">
                {check.detail}
              </Typography>
            </Box>
          </Collapse>
        )}
      </React.Fragment>
    );
  };

  return (
    <Dialog
      open={open}
      onClose={isRunning ? undefined : onCancel}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: theme => ({
          borderTop: `${theme.spacing(0.5)} solid`,
          borderColor: allPassed
            ? theme.palette.success.main
            : hasErrors || timedOut
              ? theme.palette.error.main
              : hasWarningsOnly
                ? theme.palette.warning.main
                : theme.palette.primary.main,
        }),
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <FlightTakeoffIcon color="primary" />
        Preflight Checks
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Checking endpoint connectivity, model configuration, and metric
          coverage.
        </Typography>

        {isMultiTestSet ? (
          <>
            <List dense disablePadding>
              {sharedChecks.map(renderCheckItem)}
            </List>
            {testSetGroups.map(([tsName, tsChecks]) => (
              <Box key={tsName} sx={{ mt: 1.5 }}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontWeight: 600, ml: 1, mb: 0.5, display: 'block' }}
                >
                  {tsName}
                </Typography>
                <List dense disablePadding>
                  {tsChecks.map(renderCheckItem)}
                </List>
              </Box>
            ))}
          </>
        ) : (
          <List dense disablePadding>
            {checkList.map(renderCheckItem)}
          </List>
        )}

        {allPassed && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="success.main">
              All checks passed. Ready to execute.
            </Typography>
          </Box>
        )}

        {hasErrors && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {summary.failed} check(s) failed. Fix the issues and retry before
              executing.
            </Typography>
          </Box>
        )}

        {hasWarningsOnly && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {summary.warnings} warning(s) detected. You can still proceed with
              execution.
            </Typography>
          </Box>
        )}

        {timedOut && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="body2" color="error.main">
              Preflight checks timed out. The server may be unreachable.
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        {isRunning && <Button onClick={onCancel}>Cancel</Button>}
        {timedOut && (
          <>
            <Button onClick={onCancel}>Cancel</Button>
            <Button
              onClick={onRetry}
              variant="contained"
              startIcon={<ReplayIcon />}
            >
              Retry
            </Button>
          </>
        )}
        {allPassed && (
          <>
            <Button onClick={onCancel}>Cancel</Button>
            <Button onClick={onProceed} variant="contained" color="success">
              Execute
            </Button>
          </>
        )}
        {hasErrors && (
          <>
            <Button onClick={onCancel}>Cancel</Button>
            <Button
              onClick={onRetry}
              variant="contained"
              startIcon={<ReplayIcon />}
            >
              Retry
            </Button>
          </>
        )}
        {hasWarningsOnly && (
          <>
            <Button onClick={onCancel}>Cancel</Button>
            <Button
              onClick={onRetry}
              variant="outlined"
              startIcon={<ReplayIcon />}
            >
              Retry
            </Button>
            <Button onClick={onProceed} variant="contained" color="warning">
              Execute Anyway
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
