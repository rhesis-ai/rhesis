'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Chip,
  Collapse,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { SearchIcon } from '@/components/icons';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { getSpanIcon, getSpanColor } from '@/utils/span-icon-mapper';
import { formatDuration } from '@/utils/format-duration';
import { formatTokenCount, spanUsage } from '@/utils/trace-utils';

interface SpanTreeViewProps {
  spans: SpanNode[];
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
  isConversationTrace?: boolean;
}

/** The trace's time window, which every row's bar is drawn against. */
interface Timeline {
  start: number;
  duration: number;
}

// Column widths in theme spacing units, shared by the header and every row.
const BAR_WIDTH = 22;
const DURATION_WIDTH = 7;

function timelineOf(spans: SpanNode[]): Timeline {
  let start = Infinity;
  let end = -Infinity;
  for (const span of spans) {
    start = Math.min(start, new Date(span.start_time).getTime());
    end = Math.max(end, new Date(span.end_time).getTime());
  }
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return { start: 0, duration: 1 };
  }
  return { start, duration: Math.max(end - start, 1) };
}

/**
 * Get the display name for a span, including additional context from attributes
 * when available (e.g., tool name for ai.tool.invoke spans, agent name for ai.agent.invoke)
 */
function getSpanDisplayName(span: SpanNode): string {
  const attrs = span.attributes;

  // Tool invocations: show tool name
  if (span.span_name === 'ai.tool.invoke' && attrs?.['ai.tool.name']) {
    return `${span.span_name} (${attrs['ai.tool.name']})`;
  }

  // Agent invocations: show agent name
  if (span.span_name === 'ai.agent.invoke' && attrs?.['ai.agent.name']) {
    return `${span.span_name} (${attrs['ai.agent.name']})`;
  }

  // Agent handoffs: show from -> to
  if (span.span_name === 'ai.agent.handoff') {
    const from = attrs?.['ai.agent.handoff.from'];
    const to = attrs?.['ai.agent.handoff.to'];
    if (from && to) {
      return `${span.span_name} (${from} → ${to})`;
    }
  }

  return span.span_name;
}

/** Spans whose own name matches, plus every ancestor of one, so matches keep their place. */
function matchingSpanIds(spans: SpanNode[], query: string): Set<string> {
  const ids = new Set<string>();
  const needle = query.toLowerCase();
  const visit = (span: SpanNode): boolean => {
    const own = getSpanDisplayName(span).toLowerCase().includes(needle);
    const below = (span.children ?? []).map(visit).some(Boolean);
    if (own || below) ids.add(span.span_id);
    return own || below;
  };
  spans.forEach(visit);
  return ids;
}

function formatTick(ms: number): string {
  return ms === 0 ? '0' : formatDuration(Math.round(ms));
}

export default function SpanTreeView({
  spans,
  selectedSpan,
  onSpanSelect,
  isConversationTrace,
}: SpanTreeViewProps) {
  const [query, setQuery] = useState('');
  const timeline = useMemo(() => timelineOf(spans), [spans]);
  const visible = useMemo(
    () => (query.trim() ? matchingSpanIds(spans, query.trim()) : null),
    [spans, query]
  );

  return (
    <Box>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ px: 2, pt: 1, pb: 0.5 }}>
          <TextField
            size="small"
            fullWidth
            placeholder="Filter spans"
            value={query}
            onChange={e => setQuery(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Filter spans' },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
          />
        </Box>
        <Box
          aria-hidden
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            px: 2,
            py: 0.5,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
            Span
          </Typography>
          <Box
            sx={theme => ({
              width: theme.spacing(BAR_WIDTH),
              flexShrink: 0,
              display: 'flex',
              justifyContent: 'space-between',
              fontFamily: theme.typography.fontFamilyCode,
            })}
          >
            {[0, 0.5, 1].map(f => (
              <Typography key={f} variant="caption" color="text.secondary">
                {formatTick(f * timeline.duration)}
              </Typography>
            ))}
          </Box>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              width: theme => theme.spacing(DURATION_WIDTH),
              flexShrink: 0,
              textAlign: 'right',
            }}
          >
            Duration
          </Typography>
        </Box>
      </Box>

      <Box role="tree" aria-label="Spans" sx={{ py: 0.5 }}>
        {spans
          .filter(span => !visible || visible.has(span.span_id))
          .map((span, index) => (
            <SpanTreeNode
              key={span.span_id}
              span={span}
              selectedSpan={selectedSpan}
              onSpanSelect={onSpanSelect}
              level={0}
              timeline={timeline}
              visible={visible}
              turnLabel={
                isConversationTrace && spans.length > 1
                  ? `Turn ${index + 1}`
                  : undefined
              }
            />
          ))}
        {visible && visible.size === 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', px: 2, py: 1 }}
          >
            No spans match “{query}”.
          </Typography>
        )}
      </Box>
    </Box>
  );
}

interface SpanTreeNodeProps {
  span: SpanNode;
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
  level: number;
  timeline: Timeline;
  /** Ids left by the filter, or null when nothing is filtered. */
  visible: Set<string> | null;
  turnLabel?: string;
}

function SpanTreeNode({
  span,
  selectedSpan,
  onSpanSelect,
  level,
  timeline,
  visible,
  turnLabel,
}: SpanTreeNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const children = (span.children ?? []).filter(
    child => !visible || visible.has(child.span_id)
  );
  const hasChildren = children.length > 0;
  const isSelected = selectedSpan?.span_id === span.span_id;
  const rowRef = useRef<HTMLDivElement>(null);

  // 'nearest' leaves an already visible row alone, so clicks don't jump.
  // Optional call: jsdom has no scrollIntoView.
  useEffect(() => {
    if (isSelected) rowRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [isSelected]);

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(!expanded);
  };

  const colorPath = getSpanColor(span, span.status_code);
  const SpanIcon = getSpanIcon(span);
  const usage = spanUsage(span);

  const offset =
    (new Date(span.start_time).getTime() - timeline.start) / timeline.duration;
  const width = span.duration_ms / timeline.duration;

  return (
    <Box role="none">
      <Box
        ref={rowRef}
        role="treeitem"
        aria-selected={isSelected}
        aria-level={level + 1}
        aria-expanded={hasChildren ? expanded : undefined}
        onClick={() => onSpanSelect(span)}
        data-span-id={span.span_id}
        data-selected={isSelected || undefined}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          minHeight: theme => theme.spacing(3.75),
          px: 2,
          cursor: 'pointer',
          backgroundColor: isSelected ? 'action.selected' : 'transparent',
          '&:hover': {
            backgroundColor: isSelected ? 'action.selected' : 'action.hover',
          },
        }}
      >
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            pl: level * 2,
          }}
        >
          <Box sx={{ width: theme => theme.spacing(2.5), flexShrink: 0 }}>
            {hasChildren && (
              <IconButton
                size="small"
                aria-label={expanded ? 'Collapse' : 'Expand'}
                onClick={handleToggle}
                sx={{ p: 0 }}
              >
                {expanded ? (
                  <ExpandMoreIcon fontSize="small" />
                ) : (
                  <ChevronRightIcon fontSize="small" />
                )}
              </IconButton>
            )}
          </Box>

          <Box
            component={SpanIcon}
            sx={{
              fontSize: theme => theme.spacing(2),
              color: colorPath,
              flexShrink: 0,
            }}
          />

          {turnLabel && (
            <Chip
              label={turnLabel}
              size="small"
              color="primary"
              variant="outlined"
              sx={{
                height: theme => theme.spacing(2.5),
                fontSize: theme => theme.typography.caption.fontSize,
                flexShrink: 0,
              }}
            />
          )}

          <Typography
            variant="caption"
            noWrap
            title={getSpanDisplayName(span)}
            sx={theme => ({
              fontFamily: theme.typography.fontFamilyCode,
              color: 'text.primary',
              minWidth: 0,
            })}
          >
            {getSpanDisplayName(span)}
          </Typography>

          {usage && (
            <Typography
              variant="caption"
              color="text.secondary"
              noWrap
              sx={{ flexShrink: 0 }}
            >
              {formatTokenCount(usage.total)} tok
            </Typography>
          )}

          {span.status_code === 'ERROR' && (
            <Chip
              label="ERROR"
              size="small"
              color="error"
              sx={{
                height: theme => theme.spacing(2.25),
                fontSize: theme => theme.typography.caption.fontSize,
                flexShrink: 0,
              }}
            />
          )}
        </Box>

        <Box
          aria-hidden
          sx={{
            position: 'relative',
            width: theme => theme.spacing(BAR_WIDTH),
            height: theme => theme.spacing(0.75),
            flexShrink: 0,
            borderRadius: theme => theme.spacing(0.5),
            bgcolor: 'action.hover',
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${Math.min(Math.max(offset, 0), 1) * 100}%`,
              width: `${Math.min(Math.max(width, 0), 1) * 100}%`,
              minWidth: theme => theme.spacing(0.375),
              borderRadius: theme => theme.spacing(0.5),
              bgcolor: colorPath,
              opacity: isSelected ? 1 : 0.7,
            }}
          />
        </Box>

        <Typography
          variant="caption"
          sx={theme => ({
            width: theme.spacing(DURATION_WIDTH),
            flexShrink: 0,
            textAlign: 'right',
            fontFamily: theme.typography.fontFamilyCode,
            color: 'text.primary',
          })}
        >
          {formatDuration(span.duration_ms)}
        </Typography>
      </Box>

      {hasChildren && (
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <Box role="group">
            {children.map(child => (
              <SpanTreeNode
                key={child.span_id}
                span={child}
                selectedSpan={selectedSpan}
                onSpanSelect={onSpanSelect}
                level={level + 1}
                timeline={timeline}
                visible={visible}
              />
            ))}
          </Box>
        </Collapse>
      )}
    </Box>
  );
}
