'use client';

import { useState } from 'react';
import { Box, Typography, Collapse, IconButton, Chip } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { getSpanIcon, getSpanColor } from '@/utils/span-icon-mapper';
import { formatDuration } from '@/utils/format-duration';

interface SpanTreeViewProps {
  spans: SpanNode[];
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
}

export default function SpanTreeView({
  spans,
  selectedSpan,
  onSpanSelect,
}: SpanTreeViewProps) {
  return (
    <Box>
      {spans.map(span => (
        <SpanTreeNode
          key={span.span_id}
          span={span}
          selectedSpan={selectedSpan}
          onSpanSelect={onSpanSelect}
          level={0}
        />
      ))}
    </Box>
  );
}

interface SpanTreeNodeProps {
  span: SpanNode;
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
  level: number;
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

function SpanTreeNode({
  span,
  selectedSpan,
  onSpanSelect,
  level,
}: SpanTreeNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = span.children && span.children.length > 0;
  const isSelected = selectedSpan?.span_id === span.span_id;

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(!expanded);
  };

  const handleClick = () => {
    onSpanSelect(span);
  };

  const colorPath = getSpanColor(span.span_name, span.status_code);
  const SpanIcon = getSpanIcon(span.span_name);

  return (
    <Box>
      <Box
        onClick={handleClick}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.5,
          px: 1,
          ml: level * 2,
          cursor: 'pointer',
          borderRadius: theme => theme.shape.borderRadius,
          backgroundColor: isSelected ? 'action.selected' : 'transparent',
          '&:hover': {
            backgroundColor: isSelected ? 'action.selected' : 'action.hover',
          },
        }}
      >
        {/* Expand/Collapse Icon */}
        <Box sx={{ width: theme => theme.spacing(3), flexShrink: 0 }}>
          {hasChildren && (
            <IconButton size="small" onClick={handleToggle}>
              {expanded ? (
                <ExpandMoreIcon fontSize="small" />
              ) : (
                <ChevronRightIcon fontSize="small" />
              )}
            </IconButton>
          )}
        </Box>

        {/* Semantic Icon */}
        <Box
          component={SpanIcon}
          sx={{
            fontSize: theme => theme.spacing(2.25),
            color: theme => {
              // Parse theme path (e.g., 'success.main' -> theme.palette.success.main)
              const parts = colorPath.split('.');
              if (parts.length === 2) {
                const [category, shade] = parts;
                return `${(theme.palette as any)[category]?.[shade] || colorPath} !important`;
              }
              return `${colorPath} !important`;
            },
            mr: 1,
            flexShrink: 0,
          }}
        />

        {/* Span Name and Duration */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="body2"
            sx={{
              fontFamily: 'monospace',
              fontSize: theme => theme.typography.body2.fontSize,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {getSpanDisplayName(span)}
          </Typography>
        </Box>

        {/* Duration Badge */}
        <Chip
          label={formatDuration(span.duration_ms)}
          size="small"
          sx={{
            height: theme => theme.spacing(2.5),
            fontSize: theme => theme.typography.caption.fontSize,
            ml: 1,
            flexShrink: 0,
          }}
        />

        {/* Error Indicator */}
        {span.status_code === 'ERROR' && (
          <Chip
            label="ERROR"
            size="small"
            color="error"
            sx={{
              height: theme => theme.spacing(2.5),
              fontSize: theme => theme.typography.caption.fontSize,
              ml: 0.5,
              flexShrink: 0,
            }}
          />
        )}
      </Box>

      {/* Children */}
      {hasChildren && (
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <Box
            sx={{
              position: 'relative',
              ml: 3,
              '&::before': {
                content: '""',
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: theme => theme.spacing(1),
                width: '1px',
                backgroundColor: 'divider',
              },
            }}
          >
            {span.children.map((child, _index) => (
              <Box
                key={child.span_id}
                sx={{
                  position: 'relative',
                  '&::before': {
                    content: '""',
                    position: 'absolute',
                    left: 0,
                    top: theme => theme.spacing(1.5),
                    width: theme => theme.spacing(1.5),
                    height: '1px',
                    backgroundColor: 'divider',
                  },
                }}
              >
                <SpanTreeNode
                  span={child}
                  selectedSpan={selectedSpan}
                  onSpanSelect={onSpanSelect}
                  level={level + 1}
                />
              </Box>
            ))}
          </Box>
        </Collapse>
      )}
    </Box>
  );
}
