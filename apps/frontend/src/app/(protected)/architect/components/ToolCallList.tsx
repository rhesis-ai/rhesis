'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Box, Typography, ButtonBase, Collapse } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import BuildCircleOutlinedIcon from '@mui/icons-material/BuildCircleOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { StreamingState } from '@/hooks/useArchitectChat';

const VISIBLE_COMPLETED = 2;
const FOLD_DELAY_MS = 600;
const FOLD_DURATION_MS = 300;
const ENTER_DURATION_MS = 200;

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const secs = ms / 1000;
  if (secs < 60) return `${secs.toFixed(1)}s`;
  const mins = Math.floor(secs / 60);
  const rem = Math.round(secs % 60);
  return `${mins}m ${rem}s`;
}

function ElapsedTime({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <Typography
      component="span"
      variant="caption"
      sx={{ opacity: 0.6, ml: 0.5 }}
    >
      {formatDuration(now - startedAt)}
    </Typography>
  );
}

interface ToolCallListProps {
  completedTools: StreamingState['completedTools'];
  activeTools: StreamingState['activeTools'];
}

export default function ToolCallList({
  completedTools,
  activeTools,
}: ToolCallListProps) {
  const [expandedCompleted, setExpandedCompleted] = useState(false);
  const [expandedReasoning, setExpandedReasoning] = useState<Set<number>>(
    new Set()
  );

  const prevCompletedCountRef = useRef(completedTools.length);

  useEffect(() => {
    const prevCount = prevCompletedCountRef.current;
    const newCount = completedTools.length;
    prevCompletedCountRef.current = newCount;

    if (newCount <= prevCount) return;

    const newIndices: number[] = [];
    for (let i = prevCount; i < newCount; i++) {
      if (completedTools[i]?.reasoning) newIndices.push(i);
    }
    if (newIndices.length === 0) return;

    setExpandedReasoning(prev => {
      const next = new Set(prev);
      newIndices.forEach(i => next.add(i));
      return next;
    });

    const timer = setTimeout(() => {
      setExpandedReasoning(prev => {
        const next = new Set(prev);
        newIndices.forEach(i => next.delete(i));
        return next;
      });
    }, FOLD_DELAY_MS);

    return () => clearTimeout(timer);
  }, [completedTools]);

  const hasTools = completedTools.length > 0 || activeTools.length > 0;
  if (!hasTools) return null;

  const visibleCount = activeTools.length > 0 ? 0 : VISIBLE_COMPLETED;
  const collapsedCount = completedTools.length - visibleCount;
  const shouldCollapse = collapsedCount > 0;
  const hiddenTools = shouldCollapse
    ? completedTools.slice(0, collapsedCount)
    : [];
  const visibleCompleted = shouldCollapse
    ? completedTools.slice(collapsedCount)
    : completedTools;

  const toggleReasoning = (idx: number) => {
    setExpandedReasoning(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const renderCompletedTool = (
    tool: StreamingState['completedTools'][number],
    idx: number
  ) => (
    <Collapse
      key={`done-${tool.tool}-${idx}`}
      in
      timeout={ENTER_DURATION_MS}
      appear
    >
      <Box sx={{ mb: 0.25 }}>
        <ButtonBase
          onClick={tool.reasoning ? () => toggleReasoning(idx) : undefined}
          disableRipple={!tool.reasoning}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            textAlign: 'left',
            borderRadius: 0.5,
            py: 0.125,
            cursor: tool.reasoning ? 'pointer' : 'default',
            '&:hover': tool.reasoning ? { bgcolor: 'action.hover' } : undefined,
          }}
        >
          {tool.success ? (
            <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
          ) : (
            <ErrorIcon sx={{ fontSize: 14, color: 'error.main' }} />
          )}
          <Typography
            variant="caption"
            color={tool.success ? 'text.secondary' : 'error.main'}
          >
            {tool.description || tool.tool}
          </Typography>
          {tool.durationMs != null && (
            <Typography
              component="span"
              variant="caption"
              sx={{ opacity: 0.5 }}
            >
              {formatDuration(tool.durationMs)}
            </Typography>
          )}
        </ButtonBase>
        {tool.reasoning && (
          <Collapse in={expandedReasoning.has(idx)} timeout={FOLD_DURATION_MS}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                ml: 2.5,
                mt: 0.25,
                mb: 0.5,
                fontStyle: 'italic',
                display: 'block',
              }}
            >
              {tool.reasoning}
            </Typography>
          </Collapse>
        )}
      </Box>
    </Collapse>
  );

  return (
    <Box sx={{ ml: 2.5, borderLeft: 2, borderColor: 'divider', pl: 1 }}>
      {/* Active tools first — the user cares about what's running now */}
      {activeTools.map((tool, idx) => (
        <Collapse
          key={`active-${tool.tool}-${idx}`}
          in
          timeout={ENTER_DURATION_MS}
          appear
        >
          <Box sx={{ mb: 0.25 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <BuildCircleOutlinedIcon
                sx={{
                  fontSize: 14,
                  color: 'info.main',
                  '@keyframes spin': {
                    from: { transform: 'rotate(0deg)' },
                    to: { transform: 'rotate(360deg)' },
                  },
                  animation: 'spin 2s linear infinite',
                }}
              />
              <Typography variant="caption" color="info.main">
                {tool.description || tool.tool}
              </Typography>
              <ElapsedTime startedAt={tool.startedAt} />
            </Box>
            {tool.reasoning && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  ml: 2.5,
                  mt: 0.25,
                  mb: 0.5,
                  fontStyle: 'italic',
                  display: 'block',
                }}
              >
                {tool.reasoning}
              </Typography>
            )}
          </Box>
        </Collapse>
      ))}

      {/* Collapsed summary for completed tools */}
      {shouldCollapse && (
        <ButtonBase
          onClick={() => setExpandedCompleted(prev => !prev)}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            mb: 0.25,
            py: 0.125,
            borderRadius: 0.5,
            '&:hover': { bgcolor: 'action.hover' },
          }}
        >
          <CheckCircleIcon sx={{ fontSize: 14, color: 'success.main' }} />
          <Typography variant="caption" color="text.secondary">
            {collapsedCount} completed
          </Typography>
          {expandedCompleted ? (
            <ExpandLessIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          ) : (
            <ExpandMoreIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
          )}
        </ButtonBase>
      )}

      {/* Hidden completed tools (expandable) */}
      <Collapse in={expandedCompleted} timeout={200}>
        <Box sx={{ ml: 1, borderLeft: 1, borderColor: 'divider', pl: 1 }}>
          {hiddenTools.map((tool, idx) => renderCompletedTool(tool, idx))}
        </Box>
      </Collapse>

      {/* Recent completed tools (visible when nothing is running) */}
      {visibleCompleted.map((tool, idx) =>
        renderCompletedTool(tool, collapsedCount + idx)
      )}
    </Box>
  );
}
