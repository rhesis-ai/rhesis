'use client';

import { useMemo, useCallback } from 'react';
import { Box, Typography, Chip, useTheme } from '@mui/material';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  NodeProps,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import { getSpanIcon, getSpanColor } from '@/utils/span-icon-mapper';
import { formatDuration } from '@/utils/format-duration';

interface SpanGraphViewProps {
  spans: SpanNode[];
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
}

// Node dimensions for layout calculation
const NODE_WIDTH = 280;
const NODE_HEIGHT = 60;

/**
 * Get the display name for a span, including additional context from attributes
 * (e.g., tool name for ai.tool.invoke spans, agent name for ai.agent.invoke)
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

/**
 * Custom node component for spans
 */
function SpanNodeComponent({ data, selected }: NodeProps) {
  const theme = useTheme();
  const { span, isSelected } = data;
  const SpanIcon = getSpanIcon(span.span_name);
  const colorPath = getSpanColor(span.span_name, span.status_code);

  // Parse theme color
  const getColor = () => {
    const parts = colorPath.split('.');
    if (parts.length === 2) {
      const [category, shade] = parts;
      return (theme.palette as any)[category]?.[shade] || colorPath;
    }
    return colorPath;
  };

  const nodeColor = getColor();

  return (
    <Box
      sx={{
        padding: theme.spacing(1.5),
        borderRadius: theme.shape.borderRadius,
        backgroundColor: theme.palette.background.paper,
        border: `2px solid ${isSelected ? theme.palette.primary.main : theme.palette.divider}`,
        boxShadow: isSelected ? `0 0 0 2px ${theme.palette.primary.light}` : theme.shadows[1],
        minWidth: NODE_WIDTH,
        cursor: 'pointer',
        transition: theme.transitions.create(['border-color', 'box-shadow']),
        '&:hover': {
          borderColor: theme.palette.primary.light,
          boxShadow: theme.shadows[3],
        },
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: theme.palette.divider,
          border: 'none',
          width: theme.spacing(1),
          height: theme.spacing(1),
        }}
      />

      <Box sx={{ display: 'flex', alignItems: 'center', gap: theme.spacing(1) }}>
        {/* Icon */}
        <Box
          component={SpanIcon}
          sx={{
            fontSize: theme.typography.body1.fontSize,
            color: `${nodeColor} !important`,
            flexShrink: 0,
          }}
        />

        {/* Span Name */}
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            fontSize: theme.typography.caption.fontSize,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
            fontWeight: isSelected
              ? theme.typography.fontWeightMedium
              : theme.typography.fontWeightRegular,
          }}
        >
          {getSpanDisplayName(span)}
        </Typography>

        {/* Duration */}
        <Chip
          label={formatDuration(span.duration_ms)}
          size="small"
          sx={{
            height: theme.spacing(2.5),
            fontSize: theme.typography.caption.fontSize,
            flexShrink: 0,
          }}
        />

        {/* Error indicator */}
        {span.status_code === 'ERROR' && (
          <Chip
            label="ERR"
            size="small"
            color="error"
            sx={{
              height: theme.spacing(2.5),
              fontSize: theme.typography.caption.fontSize,
              flexShrink: 0,
            }}
          />
        )}
      </Box>

      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: theme.palette.divider,
          border: 'none',
          width: theme.spacing(1),
          height: theme.spacing(1),
        }}
      />
    </Box>
  );
}

// Define custom node types
const nodeTypes = {
  spanNode: SpanNodeComponent,
};

/**
 * Convert SpanNode tree to ReactFlow nodes and edges
 */
function convertToFlowElements(
  spans: SpanNode[],
  selectedSpan: SpanNode | null,
  edgeColor: string
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  function traverse(span: SpanNode, parentId?: string) {
    const nodeId = span.span_id;

    nodes.push({
      id: nodeId,
      type: 'spanNode',
      data: {
        span,
        isSelected: selectedSpan?.span_id === span.span_id,
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    });

    if (parentId) {
      edges.push({
        id: `${parentId}-${nodeId}`,
        source: parentId,
        target: nodeId,
        type: 'smoothstep',
        animated: false,
        style: { stroke: edgeColor, strokeWidth: 1.5 },
      });
    }

    span.children?.forEach(child => traverse(child, nodeId));
  }

  spans.forEach(span => traverse(span));

  return { nodes, edges };
}

/**
 * Apply dagre layout to position nodes with optimized vertical alignment
 */
function applyDagreLayout(
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'TB'
): Node[] {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: direction,
    // Align nodes to upper-left within their rank for consistent vertical alignment
    align: 'UL',
    // Use tight-tree ranker for better tree structure layout
    ranker: 'tight-tree',
    // Horizontal spacing between nodes at the same level
    nodesep: 20,
    // Vertical spacing between levels (ranks)
    ranksep: 50,
    // Edge spacing
    edgesep: 10,
    // Margins
    marginx: 20,
    marginy: 20,
  });

  nodes.forEach(node => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach(edge => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  return nodes.map(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    };
  });
}

export default function SpanGraphView({
  spans,
  selectedSpan,
  onSpanSelect,
}: SpanGraphViewProps) {
  const theme = useTheme();

  // Convert spans to flow elements
  const { initialNodes, initialEdges } = useMemo(() => {
    const edgeColor = theme.palette.grey[400];
    const { nodes, edges } = convertToFlowElements(spans, selectedSpan, edgeColor);
    const layoutedNodes = applyDagreLayout(nodes, edges);
    return { initialNodes: layoutedNodes, initialEdges: edges };
  }, [spans, selectedSpan, theme.palette.grey]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes when selection changes
  useMemo(() => {
    setNodes(prevNodes =>
      prevNodes.map(node => ({
        ...node,
        data: {
          ...node.data,
          isSelected: selectedSpan?.span_id === node.id,
        },
      }))
    );
  }, [selectedSpan, setNodes]);

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.data?.span) {
        onSpanSelect(node.data.span);
      }
    },
    [onSpanSelect]
  );

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        minHeight: 400,
        '& .react-flow__attribution': {
          display: 'none',
        },
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
        }}
      >
        <Background color={theme.palette.divider} gap={Number(theme.spacing(2).replace('px', ''))} />
        <Controls
          style={{
            display: 'flex',
            flexDirection: 'column',
          }}
        />
        <MiniMap
          nodeColor={node => {
            if (node.data?.isSelected) {
              return theme.palette.primary.main;
            }
            if (node.data?.span?.status_code === 'ERROR') {
              return theme.palette.error.main;
            }
            return theme.palette.grey[400];
          }}
          maskColor={theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)'}
          style={{
            backgroundColor: theme.palette.background.paper,
          }}
        />
      </ReactFlow>
    </Box>
  );
}
