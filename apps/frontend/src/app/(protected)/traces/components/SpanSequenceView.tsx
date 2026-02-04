'use client';

import { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import { Box, Typography, Tooltip, useTheme } from '@mui/material';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { getSpanIcon, getSpanColor } from '@/utils/span-icon-mapper';
import { formatDuration } from '@/utils/format-duration';

interface SpanSequenceViewProps {
  spans: SpanNode[];
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
}

interface FlattenedSpan {
  span: SpanNode;
  depth: number;
  parentId?: string;
}

interface Participant {
  id: string;
  name: string;
  spanName: string;
}

/**
 * Sequence event representing either a call or return in the sequence diagram
 */
interface SequenceEvent {
  type: 'call' | 'return';
  span: SpanNode;
  parentId?: string;
  timestamp: number;
  timeString: string;
}

/**
 * Get the display name for a span
 * (e.g., tool name for ai.tool.invoke spans, agent name for ai.agent.invoke)
 */
function getSpanDisplayName(span: SpanNode): string {
  const attrs = span.attributes;

  // Tool invocations: show tool name
  if (span.span_name === 'ai.tool.invoke' && attrs?.['ai.tool.name']) {
    return attrs['ai.tool.name'];
  }

  // Agent invocations: show agent name
  if (span.span_name === 'ai.agent.invoke' && attrs?.['ai.agent.name']) {
    return attrs['ai.agent.name'];
  }

  // Agent handoffs: show from -> to
  if (span.span_name === 'ai.agent.handoff') {
    const from = attrs?.['ai.agent.handoff.from'];
    const to = attrs?.['ai.agent.handoff.to'];
    if (from && to) {
      return `${from} → ${to}`;
    }
  }

  return span.span_name;
}

/**
 * Get a short label for participant header
 */
function getParticipantLabel(span: SpanNode): string {
  const attrs = span.attributes;

  // Tool invocations: show tool name
  if (span.span_name === 'ai.tool.invoke' && attrs?.['ai.tool.name']) {
    return attrs['ai.tool.name'];
  }

  // Agent invocations: show agent name
  if (span.span_name === 'ai.agent.invoke' && attrs?.['ai.agent.name']) {
    return attrs['ai.agent.name'];
  }

  // Agent handoffs: show from -> to
  if (span.span_name === 'ai.agent.handoff') {
    const from = attrs?.['ai.agent.handoff.from'];
    const to = attrs?.['ai.agent.handoff.to'];
    if (from && to) {
      return `${from} → ${to}`;
    }
  }

  // Extract last part of span name for cleaner display
  const parts = span.span_name.split('.');
  return parts[parts.length - 1];
}

/**
 * Flatten the span tree into a time-ordered list
 */
function flattenSpans(spans: SpanNode[]): FlattenedSpan[] {
  const flattened: FlattenedSpan[] = [];

  function traverse(span: SpanNode, depth: number, parentId?: string) {
    flattened.push({ span, depth, parentId });
    span.children?.forEach(child => traverse(child, depth + 1, span.span_id));
  }

  spans.forEach(span => traverse(span, 0));

  // Sort by start time
  flattened.sort(
    (a, b) => new Date(a.span.start_time).getTime() - new Date(b.span.start_time).getTime()
  );

  return flattened;
}

/**
 * Extract unique participants (unique span operations)
 */
function extractParticipants(flattenedSpans: FlattenedSpan[]): Participant[] {
  const participantMap = new Map<string, Participant>();

  flattenedSpans.forEach(({ span }) => {
    const key = span.span_id;
    if (!participantMap.has(key)) {
      participantMap.set(key, {
        id: span.span_id,
        name: getParticipantLabel(span),
        spanName: span.span_name,
      });
    }
  });

  return Array.from(participantMap.values());
}

/**
 * Generate sequence events (calls and returns) from flattened spans
 */
function generateSequenceEvents(flattenedSpans: FlattenedSpan[]): SequenceEvent[] {
  const events: SequenceEvent[] = [];

  flattenedSpans.forEach(({ span, parentId }) => {
    // Call event - when span starts
    events.push({
      type: 'call',
      span,
      parentId,
      timestamp: new Date(span.start_time).getTime(),
      timeString: span.start_time,
    });

    // Return event - when span ends (only if it has a parent to return to)
    if (parentId) {
      events.push({
        type: 'return',
        span,
        parentId,
        timestamp: new Date(span.end_time).getTime(),
        timeString: span.end_time,
      });
    }
  });

  // Sort by timestamp
  events.sort((a, b) => a.timestamp - b.timestamp);

  return events;
}

export default function SpanSequenceView({
  spans,
  selectedSpan,
  onSpanSelect,
}: SpanSequenceViewProps) {
  const theme = useTheme();

  // Layout constants derived from theme spacing
  const PARTICIPANT_WIDTH = Number(theme.spacing(19).replace('px', '')); // ~150px
  const PARTICIPANT_GAP = Number(theme.spacing(2.5).replace('px', '')); // ~20px
  const ROW_HEIGHT = Number(theme.spacing(6.25).replace('px', '')); // ~50px
  const HEADER_HEIGHT = Number(theme.spacing(7.5).replace('px', '')); // ~60px
  const TIMELINE_WIDTH = Number(theme.spacing(10).replace('px', '')); // ~80px
  const ARROW_GAP = Number(theme.spacing(1).replace('px', '')); // ~8px
  const ARROW_HEIGHT = Number(theme.spacing(2.5).replace('px', '')); // ~20px
  const BOX_VERTICAL_PADDING = Number(theme.spacing(0.625).replace('px', '')); // ~5px
  const BORDER_WIDTH = Number(theme.spacing(0.125).replace('px', '')); // ~1px
  const BORDER_WIDTH_MEDIUM = Number(theme.spacing(0.25).replace('px', '')); // ~2px
  const DASH_SIZE = Number(theme.spacing(0.5).replace('px', '')); // ~4px
  const DASH_GAP = Number(theme.spacing(0.25).replace('px', '')); // ~2px
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // Update container width on resize
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth);
      }
    };

    updateWidth();
    const resizeObserver = new ResizeObserver(updateWidth);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, []);

  // Flatten and process spans
  const { flattenedSpans, participants, sequenceEvents, timelineStart } = useMemo(() => {
    const flattened = flattenSpans(spans);
    const parts = extractParticipants(flattened);
    const events = generateSequenceEvents(flattened);

    // Calculate timeline bounds
    let start = Infinity;
    let end = -Infinity;
    flattened.forEach(({ span }) => {
      const spanStart = new Date(span.start_time).getTime();
      const spanEnd = new Date(span.end_time).getTime();
      if (spanStart < start) start = spanStart;
      if (spanEnd > end) end = spanEnd;
    });

    return {
      flattenedSpans: flattened,
      participants: parts,
      sequenceEvents: events,
      timelineStart: start,
    };
  }, [spans]);

  // Calculate total width needed
  const totalWidth = Math.max(
    TIMELINE_WIDTH + participants.length * (PARTICIPANT_WIDTH + PARTICIPANT_GAP),
    containerWidth
  );

  // Calculate participant positions (map span_id to x position)
  const participantPositions = useMemo(() => {
    const positions = new Map<string, number>();
    participants.forEach((p, index) => {
      positions.set(p.id, TIMELINE_WIDTH + index * (PARTICIPANT_WIDTH + PARTICIPANT_GAP) + PARTICIPANT_WIDTH / 2);
    });
    return positions;
  }, [participants]);

  // Handle span click
  const handleSpanClick = useCallback(
    (span: SpanNode) => {
      onSpanSelect(span);
    },
    [onSpanSelect]
  );

  // Format time offset
  const formatTimeOffset = (timestamp: string): string => {
    const offset = new Date(timestamp).getTime() - timelineStart;
    if (offset < 1000) return `${offset}ms`;
    return `${(offset / 1000).toFixed(2)}s`;
  };

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        backgroundColor: theme.palette.background.default,
      }}
    >
      <Box
        sx={{
          minWidth: totalWidth,
          minHeight: HEADER_HEIGHT + sequenceEvents.length * ROW_HEIGHT + theme.spacing(4),
          position: 'relative',
        }}
      >
        {/* Header with participant names */}
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: theme.zIndex.appBar,
            backgroundColor: theme.palette.background.paper,
            borderBottom: `${BORDER_WIDTH}px solid ${theme.palette.divider}`,
            height: HEADER_HEIGHT,
          }}
        >
          {/* Timeline header */}
          <Box
            sx={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: TIMELINE_WIDTH,
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRight: `${BORDER_WIDTH}px solid ${theme.palette.divider}`,
            }}
          >
            <Typography
              variant="caption"
              sx={{ fontWeight: theme.typography.fontWeightMedium, color: theme.palette.text.secondary }}
            >
              Time
            </Typography>
          </Box>

          {/* Participant headers - positioned absolutely to match content */}
          {participants.map(participant => {
            const span = flattenedSpans.find(f => f.span.span_id === participant.id)?.span;
            const SpanIcon = span ? getSpanIcon(span.span_name) : null;
            const colorPath = span ? getSpanColor(span.span_name, span.status_code) : 'text.secondary';
            const headerX = participantPositions.get(participant.id) || 0;

            return (
              <Box
                key={participant.id}
                sx={{
                  position: 'absolute',
                  left: headerX - PARTICIPANT_WIDTH / 2,
                  top: 0,
                  width: PARTICIPANT_WIDTH,
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: theme.spacing(1),
                }}
              >
                {SpanIcon && (
                  <Box
                    component={SpanIcon}
                    sx={{
                      fontSize: theme.typography.body1.fontSize,
                      color: theme => {
                        const parts = colorPath.split('.');
                        if (parts.length === 2) {
                          const [category, shade] = parts;
                          return `${(theme.palette as any)[category]?.[shade] || colorPath} !important`;
                        }
                        return `${colorPath} !important`;
                      },
                      mb: 0.5,
                    }}
                  />
                )}
                <Tooltip title={participant.spanName}>
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: theme.typography.fontWeightMedium,
                      textAlign: 'center',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: '100%',
                    }}
                  >
                    {participant.name}
                  </Typography>
                </Tooltip>
              </Box>
            );
          })}
        </Box>

        {/* Lifelines (vertical dashed lines) */}
        {participants.map(participant => {
          const x = participantPositions.get(participant.id) || 0;
          return (
            <Box
              key={`lifeline-${participant.id}`}
              sx={{
                position: 'absolute',
                top: HEADER_HEIGHT,
                left: x,
                width: BORDER_WIDTH,
                height: sequenceEvents.length * ROW_HEIGHT,
                borderLeft: `${BORDER_WIDTH}px dashed ${theme.palette.divider}`,
              }}
            />
          );
        })}

        {/* Sequence rows - includes both call and return events */}
        {sequenceEvents.map((event, index) => {
          const { type, span, parentId, timeString } = event;
          const isSelected = selectedSpan?.span_id === span.span_id;
          const spanX = participantPositions.get(span.span_id) || 0;
          const parentX = parentId ? participantPositions.get(parentId) : undefined;
          const SpanIcon = getSpanIcon(span.span_name);
          const colorPath = getSpanColor(span.span_name, span.status_code);

          // Get color from theme
          const getColor = () => {
            const parts = colorPath.split('.');
            if (parts.length === 2) {
              const [category, shade] = parts;
              return (theme.palette as any)[category]?.[shade] || colorPath;
            }
            return colorPath;
          };

          const spanColor = getColor();
          const isCall = type === 'call';
          const isReturn = type === 'return';

          return (
            <Box
              key={`${span.span_id}-${type}`}
              sx={{
                position: 'absolute',
                top: HEADER_HEIGHT + index * ROW_HEIGHT,
                left: 0,
                right: 0,
                height: ROW_HEIGHT,
                display: 'flex',
                alignItems: 'center',
                backgroundColor: isSelected
                  ? theme.palette.action.selected
                  : index % 2 === 0
                    ? 'transparent'
                    : theme.palette.action.hover,
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                },
              }}
            >
              {/* Timeline column */}
              <Box
                sx={{
                  width: TIMELINE_WIDTH,
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRight: `${BORDER_WIDTH}px solid ${theme.palette.divider}`,
                  height: '100%',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: theme.typography.caption.fontSize,
                    color: theme.palette.text.secondary,
                  }}
                >
                  {formatTimeOffset(timeString)}
                </Typography>
              </Box>

              {/* Arrow rendering */}
              {parentX !== undefined && (() => {
                const boxHalfWidth = PARTICIPANT_WIDTH / 4;
                const arrowVerticalCenter = ARROW_HEIGHT / 2;
                const markerSize = Number(theme.spacing(1).replace('px', ''));
                const strokeWidth = Number(theme.spacing(0.25).replace('px', ''));

                // For calls: arrow from parent to child
                // For returns: arrow from child back to parent
                const fromX = isCall ? parentX : spanX;
                const toX = isCall ? spanX : parentX;
                const isLeftToRight = fromX < toX;

                // Arrow starts after source box, ends before target box
                const arrowStartX = isLeftToRight
                  ? fromX + boxHalfWidth + ARROW_GAP
                  : fromX - boxHalfWidth - ARROW_GAP;
                const arrowEndX = isLeftToRight
                  ? toX - boxHalfWidth - ARROW_GAP
                  : toX + boxHalfWidth + ARROW_GAP;

                const minX = Math.min(arrowStartX, arrowEndX);
                const arrowWidth = Math.abs(arrowEndX - arrowStartX);

                // Skip drawing if arrow would be too short
                if (arrowWidth < ARROW_HEIGHT) return null;

                const arrowId = `arrowhead-${span.span_id}-${type}`;

                return (
                  <svg
                    style={{
                      position: 'absolute',
                      left: minX,
                      top: ROW_HEIGHT / 2 - arrowVerticalCenter,
                      width: arrowWidth,
                      height: ARROW_HEIGHT,
                      overflow: 'visible',
                    }}
                  >
                    <defs>
                      <marker
                        id={arrowId}
                        markerWidth={markerSize}
                        markerHeight={markerSize * 0.75}
                        refX={markerSize - 1}
                        refY={markerSize * 0.375}
                        orient="auto"
                      >
                        <polygon
                          points={`0 0, ${markerSize} ${markerSize * 0.375}, 0 ${markerSize * 0.75}`}
                          fill={isReturn ? theme.palette.grey[500] : spanColor}
                        />
                      </marker>
                    </defs>
                    <line
                      x1={isLeftToRight ? 0 : arrowWidth}
                      y1={arrowVerticalCenter}
                      x2={isLeftToRight ? arrowWidth : 0}
                      y2={arrowVerticalCenter}
                      stroke={isReturn ? theme.palette.grey[500] : spanColor}
                      strokeWidth={strokeWidth}
                      strokeDasharray={isReturn ? `${DASH_SIZE} ${DASH_GAP}` : 'none'}
                      markerEnd={`url(#${arrowId})`}
                    />
                  </svg>
                );
              })()}

              {/* Activation box - only for call events */}
              {isCall && (
                <Tooltip
                  title={
                    <>
                      <strong>{getSpanDisplayName(span)}</strong>
                      <br />
                      Duration: {formatDuration(span.duration_ms)}
                      {span.attributes?.['ai.tool.name'] && (
                        <>
                          <br />
                          Tool: {span.attributes['ai.tool.name']}
                        </>
                      )}
                      {span.attributes?.['ai.input'] && (
                        <>
                          <br />
                          Input: {String(span.attributes['ai.input']).substring(0, 100)}...
                        </>
                      )}
                    </>
                  }
                >
                  <Box
                    onClick={() => handleSpanClick(span)}
                    sx={{
                      position: 'absolute',
                      left: spanX - PARTICIPANT_WIDTH / 4,
                      width: PARTICIPANT_WIDTH / 2,
                      height: ROW_HEIGHT - BOX_VERTICAL_PADDING * 2,
                      top: BOX_VERTICAL_PADDING,
                      backgroundColor: isSelected ? theme.palette.primary.main : spanColor,
                      opacity: isSelected ? 1 : 0.8,
                      borderRadius: theme.shape.borderRadius,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: theme.spacing(0.5),
                      padding: theme.spacing(0.5),
                      border: isSelected
                        ? `${BORDER_WIDTH_MEDIUM}px solid ${theme.palette.primary.dark}`
                        : 'none',
                      transition: theme.transitions.create(['opacity', 'background-color']),
                      '&:hover': {
                        opacity: 1,
                      },
                    }}
                  >
                    <Box
                      component={SpanIcon}
                      sx={{
                        fontSize: theme.typography.caption.fontSize,
                        color: `${theme.palette.common.white} !important`,
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        color: theme.palette.common.white,
                        fontSize: theme.spacing(1.25),
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {formatDuration(span.duration_ms)}
                    </Typography>
                  </Box>
                </Tooltip>
              )}

              {/* Return marker - small circle at return point for return events */}
              {isReturn && parentX !== undefined && (() => {
                const markerRadius = Number(theme.spacing(1).replace('px', ''));
                return (
                  <Tooltip title={`${getSpanDisplayName(span)} returned`}>
                    <Box
                      onClick={() => handleSpanClick(span)}
                      sx={{
                        position: 'absolute',
                        left: parentX - markerRadius,
                        top: ROW_HEIGHT / 2 - markerRadius,
                        width: theme.spacing(2),
                        height: theme.spacing(2),
                        borderRadius: '50%',
                        backgroundColor: theme.palette.grey[400],
                        border: `${BORDER_WIDTH_MEDIUM}px solid ${theme.palette.grey[500]}`,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: theme.transitions.create(['background-color']),
                        '&:hover': {
                          backgroundColor: theme.palette.grey[500],
                        },
                      }}
                    />
                  </Tooltip>
                );
              })()}

              {/* Error indicator - only for call events */}
              {isCall && span.status_code === 'ERROR' && (
                <Box
                  sx={{
                    position: 'absolute',
                    left: spanX + PARTICIPANT_WIDTH / 4 + BOX_VERTICAL_PADDING,
                    top: ROW_HEIGHT / 2 - Number(theme.spacing(1).replace('px', '')),
                    width: theme.spacing(2),
                    height: theme.spacing(2),
                    borderRadius: '50%',
                    backgroundColor: theme.palette.error.main,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Typography
                    sx={{
                      color: theme.palette.common.white,
                      fontSize: theme.spacing(1.25),
                      fontWeight: theme.typography.fontWeightBold,
                    }}
                  >
                    !
                  </Typography>
                </Box>
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
