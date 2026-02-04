'use client';

import { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Chip,
  useTheme,
  Slider,
  IconButton,
  Paper,
  Stack,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import ReplayIcon from '@mui/icons-material/Replay';
import FastForwardIcon from '@mui/icons-material/FastForward';
import FastRewindIcon from '@mui/icons-material/FastRewind';
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
  EdgeProps,
  getBezierPath,
  MarkerType,
  Viewport,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';
import BuildIcon from '@mui/icons-material/Build';

interface SpanMarkovViewProps {
  spans: SpanNode[];
  selectedSpan: SpanNode | null;
  onSpanSelect: (span: SpanNode) => void;
}

// Node dimensions for layout calculation
const NODE_WIDTH = 180;
const NODE_HEIGHT = 80;

// Interface for tracking state transitions with timestamp
interface StateTransition {
  from: string;
  to: string;
  count: number;
}

// Interface for timed transition events
interface TimedTransition {
  from: string;
  to: string;
  timestamp: number;
  spanId: string;
}

// Interface for timed agent appearances
interface TimedAgentEvent {
  agentName: string;
  timestamp: number;
  spanId: string;
}

// Interface for Markov state (agent or tool)
interface MarkovState {
  id: string;
  name: string;
  type: 'agent' | 'tool';
  invocationCount: number;
  totalDurationMs: number;
  hasError: boolean;
  firstAppearance: number;
}

/**
 * Extract agent and tool states and transitions from spans with timestamps
 */
function extractMarkovChain(spans: SpanNode[]): {
  states: Map<string, MarkovState>;
  transitions: StateTransition[];
  timedTransitions: TimedTransition[];
  timedAgentEvents: TimedAgentEvent[];
  timeRange: { start: number; end: number };
} {
  const states = new Map<string, MarkovState>();
  const transitionCounts = new Map<string, number>();
  const entitySequence: {
    name: string;
    timestamp: number;
    spanId: string;
    type: 'agent' | 'tool';
  }[] = [];
  const timedTransitions: TimedTransition[] = [];
  const timedAgentEvents: TimedAgentEvent[] = [];
  let minTime = Infinity;
  let maxTime = -Infinity;

  // First pass: collect all agent invocations with their time ranges
  const agentTimeRanges: {
    name: string;
    startTime: number;
    endTime: number;
    spanId: string;
  }[] = [];

  // Also collect all tools and handoffs for later processing
  const toolInvocations: {
    toolId: string;
    toolName: string;
    startTime: number;
    endTime: number;
    spanId: string;
    hasError: boolean;
    durationMs: number;
  }[] = [];

  const handoffs: {
    from: string;
    to: string;
    timestamp: number;
    spanId: string;
  }[] = [];

  // Flatten all spans and collect data
  function collectSpans(span: SpanNode) {
    const spanTime = new Date(span.start_time).getTime();
    const spanEndTime = new Date(span.end_time).getTime();
    minTime = Math.min(minTime, spanTime);
    maxTime = Math.max(maxTime, spanEndTime);

    // Collect agent invocations
    if (span.span_name === 'ai.agent.invoke') {
      const agentName = span.attributes?.['ai.agent.name'] as string;
      if (agentName) {
        agentTimeRanges.push({
          name: agentName,
          startTime: spanTime,
          endTime: spanEndTime,
          spanId: span.span_id,
        });

        // Add to sequence for transition tracking
        entitySequence.push({
          name: agentName,
          timestamp: spanTime,
          spanId: span.span_id,
          type: 'agent',
        });

        // Add timed agent event
        timedAgentEvents.push({
          agentName,
          timestamp: spanTime,
          spanId: span.span_id,
        });

        // Update or create state
        const existing = states.get(agentName);
        if (existing) {
          existing.invocationCount++;
          existing.totalDurationMs += span.duration_ms;
          existing.hasError = existing.hasError || span.status_code === 'ERROR';
          existing.firstAppearance = Math.min(
            existing.firstAppearance,
            spanTime
          );
        } else {
          states.set(agentName, {
            id: agentName,
            name: agentName,
            type: 'agent',
            invocationCount: 1,
            totalDurationMs: span.duration_ms,
            hasError: span.status_code === 'ERROR',
            firstAppearance: spanTime,
          });
        }
      }
    }

    // Collect tool invocations
    if (span.span_name === 'ai.tool.invoke') {
      const toolName = span.attributes?.['ai.tool.name'] as string;
      if (toolName) {
        toolInvocations.push({
          toolId: `tool:${toolName}`,
          toolName,
          startTime: spanTime,
          endTime: spanEndTime,
          spanId: span.span_id,
          hasError: span.status_code === 'ERROR',
          durationMs: span.duration_ms,
        });
      }
    }

    // Collect handoffs
    if (span.span_name === 'ai.agent.handoff') {
      const from = span.attributes?.['ai.agent.handoff.from'] as string;
      const to = span.attributes?.['ai.agent.handoff.to'] as string;
      if (from && to) {
        handoffs.push({
          from,
          to,
          timestamp: spanTime,
          spanId: span.span_id,
        });
      }
    }

    // Recurse into children
    span.children?.forEach(child => collectSpans(child));
  }

  spans.forEach(span => collectSpans(span));

  // Sort agent time ranges by start time
  agentTimeRanges.sort((a, b) => a.startTime - b.startTime);

  // Sort tool invocations by start time
  toolInvocations.sort((a, b) => a.startTime - b.startTime);

  // Helper: find the agent that called a tool
  // The calling agent is the most recently invoked agent BEFORE the tool started
  // In the trace pattern: agent invokes -> tool executes -> agent resumes
  // The tool is called by whichever agent was most recently active
  function findCallingAgent(toolStartTime: number): string | null {
    // Find the agent invocation that started most recently before the tool
    let callingAgent: string | null = null;
    let latestAgentStart = -Infinity;

    for (const agent of agentTimeRanges) {
      // Agent must have started before the tool
      if (
        agent.startTime < toolStartTime &&
        agent.startTime > latestAgentStart
      ) {
        latestAgentStart = agent.startTime;
        callingAgent = agent.name;
      }
    }

    return callingAgent;
  }

  // Process tool invocations - find the calling agent based on sequence
  for (const tool of toolInvocations) {
    const callingAgent = findCallingAgent(tool.startTime);

    // Add to sequence
    entitySequence.push({
      name: tool.toolId,
      timestamp: tool.startTime,
      spanId: tool.spanId,
      type: 'tool',
    });

    // Add timed event
    timedAgentEvents.push({
      agentName: tool.toolId,
      timestamp: tool.startTime,
      spanId: tool.spanId,
    });

    // Update or create tool state
    const existing = states.get(tool.toolId);
    if (existing) {
      existing.invocationCount++;
      existing.totalDurationMs += tool.durationMs;
      existing.hasError = existing.hasError || tool.hasError;
      existing.firstAppearance = Math.min(
        existing.firstAppearance,
        tool.startTime
      );
    } else {
      states.set(tool.toolId, {
        id: tool.toolId,
        name: tool.toolName,
        type: 'tool',
        invocationCount: 1,
        totalDurationMs: tool.durationMs,
        hasError: tool.hasError,
        firstAppearance: tool.startTime,
      });
    }

    // Create transitions if we found a calling agent
    if (callingAgent) {
      // Agent -> Tool transition
      const agentToToolKey = `${callingAgent}->${tool.toolId}`;
      transitionCounts.set(
        agentToToolKey,
        (transitionCounts.get(agentToToolKey) || 0) + 1
      );

      timedTransitions.push({
        from: callingAgent,
        to: tool.toolId,
        timestamp: tool.startTime,
        spanId: tool.spanId,
      });

      // Tool -> Agent return transition
      const toolToAgentKey = `${tool.toolId}->${callingAgent}`;
      transitionCounts.set(
        toolToAgentKey,
        (transitionCounts.get(toolToAgentKey) || 0) + 1
      );

      timedTransitions.push({
        from: tool.toolId,
        to: callingAgent,
        timestamp: tool.endTime,
        spanId: tool.spanId,
      });
    }
  }

  // Process handoffs
  for (const handoff of handoffs) {
    const key = `${handoff.from}->${handoff.to}`;
    transitionCounts.set(key, (transitionCounts.get(key) || 0) + 1);

    timedTransitions.push({
      from: handoff.from,
      to: handoff.to,
      timestamp: handoff.timestamp,
      spanId: handoff.spanId,
    });

    // Ensure states exist
    if (!states.has(handoff.from)) {
      states.set(handoff.from, {
        id: handoff.from,
        name: handoff.from,
        type: 'agent',
        invocationCount: 0,
        totalDurationMs: 0,
        hasError: false,
        firstAppearance: handoff.timestamp,
      });
    }
    if (!states.has(handoff.to)) {
      states.set(handoff.to, {
        id: handoff.to,
        name: handoff.to,
        type: 'agent',
        invocationCount: 0,
        totalDurationMs: 0,
        hasError: false,
        firstAppearance: handoff.timestamp,
      });
    }
  }

  // Sort entity sequence by timestamp
  entitySequence.sort((a, b) => a.timestamp - b.timestamp);

  // Note: We intentionally DON'T create agent-to-agent self-loops here.
  // What looks like "safety_specialist → safety_specialist" is actually:
  // "safety_specialist → tool → safety_specialist"
  // The tool transitions (created above) correctly capture these cycles.
  // Agent-to-agent transitions only happen via explicit handoffs (also handled above).

  // Sort timed transitions by timestamp
  timedTransitions.sort((a, b) => a.timestamp - b.timestamp);
  timedAgentEvents.sort((a, b) => a.timestamp - b.timestamp);

  // Convert to transitions array
  const transitions: StateTransition[] = [];
  transitionCounts.forEach((count, key) => {
    const [from, to] = key.split('->');
    transitions.push({ from, to, count });
  });

  return {
    states,
    transitions,
    timedTransitions,
    timedAgentEvents,
    timeRange: {
      start: minTime === Infinity ? 0 : minTime,
      end: maxTime === -Infinity ? 0 : maxTime,
    },
  };
}


/**
 * Custom node component for Markov states (agents and tools)
 */
function MarkovStateNode({ data }: NodeProps) {
  const theme = useTheme();
  const { state, isSelected } = data as {
    state: MarkovState;
    isSelected: boolean;
  };

  const isAgent = state.type === 'agent';
  const stateColor = isAgent
    ? theme.palette.info.main
    : theme.palette.warning.main;

  const avgDuration =
    state.invocationCount > 0
      ? state.totalDurationMs / state.invocationCount
      : 0;

  const formatDuration = (ms: number) => {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  // Tool nodes are pill/stadium shaped (rectangle with semi-circular sides)
  const toolWidth = 180;
  const toolHeight = 48;

  return (
    <Box
      sx={{
        padding: isAgent ? theme.spacing(2) : theme.spacing(1, 2),
        // Pill shape for tools (border-radius = half height), rounded rect for agents
        borderRadius: isAgent ? theme.spacing(1) : toolHeight / 2,
        backgroundColor: theme.palette.background.paper,
        border: `2px solid ${isSelected ? theme.palette.primary.main : stateColor}`,
        boxShadow: isSelected
          ? `0 0 0 3px ${theme.palette.primary.light}`
          : theme.shadows[1],
        width: isAgent ? NODE_WIDTH : toolWidth,
        height: isAgent ? 'auto' : toolHeight,
        minWidth: isAgent ? NODE_WIDTH : toolWidth,
        minHeight: isAgent ? NODE_HEIGHT : toolHeight,
        cursor: 'pointer',
        transition: theme.transitions.create(['border-color', 'box-shadow']),
        '&:hover': {
          borderColor: theme.palette.primary.light,
          boxShadow: theme.shadows[4],
        },
        display: 'flex',
        flexDirection: isAgent ? 'column' : 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: theme.spacing(0.5),
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: stateColor,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        style={{
          background: stateColor,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />

      {/* Icon - Agent or Tool */}
      {isAgent ? (
        <SupportAgentIcon
          sx={{
            fontSize: theme.spacing(3),
            color: state.hasError ? theme.palette.error.main : stateColor,
          }}
        />
      ) : (
        <BuildIcon
          sx={{
            fontSize: theme.spacing(2.5),
            color: state.hasError ? theme.palette.error.main : stateColor,
            flexShrink: 0,
          }}
        />
      )}

      {/* State Name */}
      <Typography
        variant={isAgent ? 'subtitle2' : 'body2'}
        sx={{
          fontWeight: isAgent
            ? theme.typography.fontWeightBold
            : theme.typography.fontWeightMedium,
          textAlign: 'center',
          color: state.hasError
            ? theme.palette.error.main
            : theme.palette.text.primary,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: isAgent ? 'none' : theme.spacing(15),
          lineHeight: 1.2,
        }}
      >
        {state.name}
      </Typography>

      {/* Stats - only show for agents */}
      {isAgent && (
        <Box
          sx={{
            display: 'flex',
            gap: theme.spacing(0.5),
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}
        >
          <Chip
            label={`${state.invocationCount}x`}
            size="small"
            sx={{
              height: theme.spacing(2.5),
              fontSize: theme.typography.caption.fontSize,
              backgroundColor: theme.palette.info.light,
              color: theme.palette.info.contrastText,
            }}
          />
          <Chip
            label={`avg: ${formatDuration(avgDuration)}`}
            size="small"
            sx={{
              height: theme.spacing(2.5),
              fontSize: theme.typography.caption.fontSize,
            }}
          />
        </Box>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: stateColor,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{
          background: stateColor,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />
    </Box>
  );
}

/**
 * Custom edge component for transitions
 */
function TransitionEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style,
}: EdgeProps) {
  const { isSelfLoop, selfLoopIndex } = data as {
    isSelfLoop: boolean;
    selfLoopIndex?: number;
  };

  // For self-loops, create a custom path with offset based on index
  // All loops start and end at the same points, but curve outward at different radii
  if (isSelfLoop) {
    const baseRadius = 35;
    const radiusIncrement = 18;
    const index = selfLoopIndex || 0;
    const loopRadius = baseRadius + index * radiusIncrement;

    // All arrows start and end at the same position
    // Only the control points (curve apex) are offset
    const path = `M ${sourceX} ${sourceY} 
                  C ${sourceX + loopRadius * 2} ${sourceY - loopRadius} 
                    ${sourceX + loopRadius * 2} ${sourceY + loopRadius} 
                    ${targetX} ${targetY}`;

    return (
      <>
        {/* Invisible wider path for easier clicking */}
        <path
          d={path}
          style={{
            fill: 'none',
            stroke: 'transparent',
            strokeWidth: 20,
            cursor: 'pointer',
          }}
        />
        <path
          id={id}
          className="react-flow__edge-path"
          d={path}
          style={{
            ...style,
            fill: 'none',
            cursor: 'pointer',
          }}
          markerEnd={markerEnd}
        />
      </>
    );
  }

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.25,
  });

  return (
    <>
      {/* Invisible wider path for easier clicking */}
      <path
        d={edgePath}
        style={{
          fill: 'none',
          stroke: 'transparent',
          strokeWidth: 20,
          cursor: 'pointer',
        }}
      />
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{
          ...style,
          fill: 'none',
          cursor: 'pointer',
        }}
        markerEnd={markerEnd}
      />
    </>
  );
}

// Define custom node and edge types
const nodeTypes = {
  markovState: MarkovStateNode,
};

const edgeTypes = {
  transition: TransitionEdge,
};

/**
 * Convert agent/tool graph to ReactFlow elements
 */
function convertToFlowElements(
  states: Map<string, MarkovState>,
  transitions: StateTransition[],
  agentEdgeColor: string,
  toolEdgeColor: string
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Create nodes for each state
  states.forEach((state, id) => {
    nodes.push({
      id,
      type: 'markovState',
      data: {
        state,
        isSelected: false,
      },
      position: { x: 0, y: 0 }, // Will be set by layout
    });
  });

  // Create edges for transitions
  transitions.forEach(t => {
    const isSelfLoop = t.from === t.to;

    // Determine if this transition involves a tool
    const involvesTool = t.from.startsWith('tool:') || t.to.startsWith('tool:');
    const edgeColor = involvesTool ? toolEdgeColor : agentEdgeColor;

    if (isSelfLoop && t.count > 1) {
      // Create multiple self-loop edges with different offsets
      for (let i = 0; i < t.count; i++) {
        edges.push({
          id: `${t.from}->${t.to}-${i}`,
          source: t.from,
          target: t.to,
          type: 'transition',
          sourceHandle: 'right',
          targetHandle: 'left',
          data: {
            isSelfLoop: true,
            selfLoopIndex: i,
            selfLoopTotal: t.count,
            involvesTool,
          },
          style: {
            stroke: edgeColor,
            strokeWidth: 2,
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: edgeColor,
          },
        });
      }
    } else {
      // Single edge (either non-self-loop or single self-loop)
      edges.push({
        id: `${t.from}->${t.to}`,
        source: t.from,
        target: t.to,
        type: 'transition',
        sourceHandle: isSelfLoop ? 'right' : undefined,
        targetHandle: isSelfLoop ? 'left' : undefined,
        data: {
          isSelfLoop,
          selfLoopIndex: 0,
          selfLoopTotal: 1,
          involvesTool,
        },
        style: {
          stroke: edgeColor,
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeColor,
        },
      });
    }
  });

  return { nodes, edges };
}

// Tool node dimensions (pill/stadium shape)
const TOOL_WIDTH = 180;
const TOOL_HEIGHT = 48;

/**
 * Apply dagre layout to position nodes
 */
function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  if (nodes.length === 0) return nodes;

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: 'TB', // Top to bottom for better tool visualization
    align: 'UL',
    ranker: 'network-simplex',
    nodesep: 60,
    ranksep: 80,
    edgesep: 30,
    marginx: 50,
    marginy: 50,
  });

  nodes.forEach(node => {
    const isTool = node.id.startsWith('tool:');
    const width = isTool ? TOOL_WIDTH : NODE_WIDTH;
    const height = isTool ? TOOL_HEIGHT : NODE_HEIGHT;
    dagreGraph.setNode(node.id, { width, height });
  });

  // Filter out self-loops for layout purposes
  edges
    .filter(e => e.source !== e.target)
    .forEach(edge => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

  dagre.layout(dagreGraph);

  return nodes.map(node => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const isTool = node.id.startsWith('tool:');
    const width = isTool ? TOOL_WIDTH : NODE_WIDTH;
    const height = isTool ? TOOL_HEIGHT : NODE_HEIGHT;
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - width / 2,
        y: nodeWithPosition.y - height / 2,
      },
    };
  });
}

export default function SpanMarkovView({
  spans,
  selectedSpan,
  onSpanSelect,
}: SpanMarkovViewProps) {
  const theme = useTheme();

  // Extract graph data from spans with time data
  const {
    states,
    transitions,
    initialNodes,
    initialEdges,
    timedTransitions,
    timedAgentEvents,
    timeRange,
    defaultViewport,
  } = useMemo(() => {
    const {
      states,
      transitions,
      timedTransitions,
      timedAgentEvents,
      timeRange,
    } = extractMarkovChain(spans);
    const agentEdgeColor = theme.palette.info.main;
    const toolEdgeColor = theme.palette.warning.main;
    const { nodes, edges } = convertToFlowElements(
      states,
      transitions,
      agentEdgeColor,
      toolEdgeColor
    );
    const layoutedNodes = applyDagreLayout(nodes, edges);
    
    // Calculate viewport that fits all nodes (for initial zoom level)
    // This ensures the graph is properly zoomed even when starting at time zero
    let defaultViewport: Viewport = { x: 0, y: 0, zoom: 1 };
    if (layoutedNodes.length > 0) {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      layoutedNodes.forEach(node => {
        const isTool = node.id.startsWith('tool:');
        const width = isTool ? TOOL_WIDTH : NODE_WIDTH;
        const height = isTool ? TOOL_HEIGHT : NODE_HEIGHT;
        minX = Math.min(minX, node.position.x);
        minY = Math.min(minY, node.position.y);
        maxX = Math.max(maxX, node.position.x + width);
        maxY = Math.max(maxY, node.position.y + height);
      });
      
      // Add padding
      const padding = 50;
      minX -= padding;
      minY -= padding;
      maxX += padding;
      maxY += padding;
      
      // Calculate zoom to fit (assuming container is roughly 800x600)
      // We'll use a conservative estimate and let ReactFlow adjust
      const graphWidth = maxX - minX;
      const graphHeight = maxY - minY;
      const containerWidth = 800;
      const containerHeight = 500;
      const zoom = Math.min(
        containerWidth / graphWidth,
        containerHeight / graphHeight,
        1 // Don't zoom in more than 1x
      ) * 0.9; // 90% to leave some margin
      
      // Center the graph
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      defaultViewport = {
        x: containerWidth / 2 - centerX * zoom,
        y: containerHeight / 2 - centerY * zoom,
        zoom,
      };
    }
    
    return {
      states,
      transitions,
      initialNodes: layoutedNodes,
      initialEdges: edges,
      timedTransitions,
      timedAgentEvents,
      timeRange,
      defaultViewport,
    };
  }, [spans, theme.palette.info.main, theme.palette.warning.main]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Time slider state
  const [currentTime, setCurrentTime] = useState(timeRange.start);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const animationRef = useRef<number | null>(null);
  const lastFrameTime = useRef<number>(0);

  // Duration of the trace in ms
  const traceDuration = timeRange.end - timeRange.start;

  // Reset to start when spans change (start with empty graph)
  useEffect(() => {
    setCurrentTime(timeRange.start);
    setIsPlaying(false);
  }, [spans, timeRange.start]);

  // Animation loop for playback
  useEffect(() => {
    if (!isPlaying) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
      return;
    }

    const animate = (timestamp: number) => {
      if (!lastFrameTime.current) {
        lastFrameTime.current = timestamp;
      }

      const deltaTime = timestamp - lastFrameTime.current;
      lastFrameTime.current = timestamp;

      // Advance time based on playback speed (real-time playback scaled)
      // 1x speed = 10 seconds to play through entire trace
      const playbackDuration = 10000 / playbackSpeed;
      const timeIncrement = (traceDuration / playbackDuration) * deltaTime;

      setCurrentTime(prev => {
        const newTime = prev + timeIncrement;
        if (newTime >= timeRange.end) {
          setIsPlaying(false);
          return timeRange.end;
        }
        return newTime;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    lastFrameTime.current = 0;
    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, playbackSpeed, traceDuration, timeRange.end]);

  // Update visible nodes and edges based on current time
  useEffect(() => {
    // Find which agents have appeared by current time
    const visibleAgents = new Set<string>();
    timedAgentEvents.forEach(event => {
      if (event.timestamp <= currentTime) {
        visibleAgents.add(event.agentName);
      }
    });

    // Find which transitions have occurred by current time and track the last one
    const transitionCounts = new Map<string, number>();
    let lastTransition: { from: string; to: string; index: number } | null =
      null;

    timedTransitions.forEach(t => {
      if (t.timestamp <= currentTime) {
        const key = `${t.from}->${t.to}`;
        const currentCount = transitionCounts.get(key) || 0;
        transitionCounts.set(key, currentCount + 1);
        // Track the last transition (most recent by timestamp)
        lastTransition = {
          from: t.from,
          to: t.to,
          index: currentCount, // 0-based index for this specific transition
        };
      }
    });

    // Update nodes visibility
    setNodes(prevNodes =>
      prevNodes.map(node => ({
        ...node,
        hidden: !visibleAgents.has(node.id),
        style: {
          ...node.style,
          opacity: visibleAgents.has(node.id) ? 1 : 0,
        },
      }))
    );

    // Update edges based on transitions that have occurred
    setEdges(prevEdges =>
      prevEdges.map(edge => {
        const baseKey = `${edge.source}->${edge.target}`;
        const count = transitionCounts.get(baseKey) || 0;

        // Check if this edge is the last transition
        const isLastTransition =
          lastTransition &&
          edge.source === lastTransition.from &&
          edge.target === lastTransition.to;

        // For self-loops, show based on index
        if (edge.data?.isSelfLoop && edge.data?.selfLoopIndex !== undefined) {
          const shouldShow = edge.data.selfLoopIndex < count;
          // Only animate if this is the last transition AND this specific self-loop index
          const shouldAnimate = Boolean(
            isLastTransition &&
            edge.data.selfLoopIndex === lastTransition!.index
          );
          return {
            ...edge,
            hidden: !shouldShow,
            animated: shouldAnimate,
            style: {
              ...edge.style,
              opacity: shouldShow ? 1 : 0,
            },
          };
        }

        // For regular edges
        const shouldShow = count > 0;
        // Only animate if this is the very last transition
        const shouldAnimate = Boolean(
          isLastTransition && !edge.data?.isSelfLoop
        );
        return {
          ...edge,
          hidden: !shouldShow,
          animated: shouldAnimate,
          style: {
            ...edge.style,
            opacity: shouldShow ? 1 : 0,
          },
        };
      })
    );
  }, [currentTime, timedAgentEvents, timedTransitions, setNodes, setEdges]);

  // Playback controls
  const handlePlayPause = () => {
    if (!isPlaying) {
      // Starting playback - only reset to start if already at the end
      if (currentTime >= timeRange.end) {
        // Reset to start first, then start playing after a brief delay
        // to ensure React has processed the time reset
        setCurrentTime(timeRange.start);
        setTimeout(() => setIsPlaying(true), 0);
        return;
      }
      // Otherwise continue from current position
    }
    setIsPlaying(!isPlaying);
  };

  const handleReset = () => {
    setIsPlaying(false);
    setCurrentTime(timeRange.start);
  };

  const handleSliderChange = (_: Event, value: number | number[]) => {
    setIsPlaying(false);
    setCurrentTime(value as number);
  };

  const handleSpeedChange = () => {
    // Cycle through speeds: 1x -> 2x -> 4x -> 1x
    setPlaybackSpeed(prev => (prev >= 4 ? 1 : prev * 2));
  };

  // Format time for display
  const formatTime = (ms: number) => {
    const totalSeconds = Math.floor((ms - timeRange.start) / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const milliseconds = Math.floor((ms - timeRange.start) % 1000);
    if (minutes > 0) {
      return `${minutes}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0').slice(0, 1)}`;
    }
    return `${seconds}.${milliseconds.toString().padStart(3, '0').slice(0, 1)}s`;
  };

  // Handle node click - find an agent or tool span with this name
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const nodeId = node.id;
      const isTool = nodeId.startsWith('tool:');
      const name = isTool ? nodeId.replace('tool:', '') : nodeId;

      function findSpan(spans: SpanNode[]): SpanNode | null {
        for (const span of spans) {
          // Find agent span
          if (
            !isTool &&
            span.span_name === 'ai.agent.invoke' &&
            span.attributes?.['ai.agent.name'] === name
          ) {
            return span;
          }
          // Find tool span
          if (
            isTool &&
            span.span_name === 'ai.tool.invoke' &&
            span.attributes?.['ai.tool.name'] === name
          ) {
            return span;
          }
          if (span.children) {
            const found = findSpan(span.children);
            if (found) return found;
          }
        }
        return null;
      }
      const foundSpan = findSpan(spans);
      if (foundSpan) {
        onSpanSelect(foundSpan);
      }
    },
    [spans, onSpanSelect]
  );

  // Handle edge click - find the corresponding handoff, agent, or tool span
  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const sourceId = edge.source;
      const targetId = edge.target;
      const isSelfLoop = sourceId === targetId;
      const targetIsTool = targetId.startsWith('tool:');
      const targetName = targetIsTool
        ? targetId.replace('tool:', '')
        : targetId;

      function findSpan(spans: SpanNode[]): SpanNode | null {
        for (const span of spans) {
          // For transitions to tools, find the tool span
          if (targetIsTool && span.span_name === 'ai.tool.invoke') {
            const toolName = span.attributes?.['ai.tool.name'];
            if (toolName === targetName) {
              return span;
            }
          }

          // For transitions between different agents, look for handoff spans
          if (
            !isSelfLoop &&
            !targetIsTool &&
            span.span_name === 'ai.agent.handoff'
          ) {
            const from = span.attributes?.['ai.agent.handoff.from'];
            const to = span.attributes?.['ai.agent.handoff.to'];
            if (from === sourceId && to === targetId) {
              return span;
            }
          }

          // For self-loops on agents, find the target agent's invoke span
          if (
            isSelfLoop &&
            !targetIsTool &&
            span.span_name === 'ai.agent.invoke'
          ) {
            const agentName = span.attributes?.['ai.agent.name'];
            if (agentName === targetId) {
              return span;
            }
          }

          // Traverse children
          if (span.children) {
            const found = findSpan(span.children);
            if (found) return found;
          }
        }
        return null;
      }

      const foundSpan = findSpan(spans);
      if (foundSpan) {
        onSpanSelect(foundSpan);
      }
    },
    [spans, onSpanSelect]
  );

  // Show message if no agent data
  if (states.size === 0) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: theme.spacing(2),
        }}
      >
        <SupportAgentIcon
          sx={{ fontSize: theme.spacing(6), color: theme.palette.grey[400] }}
        />
        <Typography color="text.secondary">
          No agent data found in this trace
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Graph view requires ai.agent.invoke or ai.tool.invoke spans
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        minHeight: theme.spacing(50),
        display: 'flex',
        flexDirection: 'column',
        '& .react-flow__attribution': {
          display: 'none',
        },
      }}
    >
      {/* Time Slider Controls */}
      <Paper
        elevation={0}
        sx={{
          px: theme.spacing(2),
          py: theme.spacing(1),
          borderBottom: `1px solid ${theme.palette.divider}`,
          backgroundColor: theme.palette.background.paper,
          zIndex: theme.zIndex.appBar,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          {/* Reset Button */}
          <IconButton
            size="small"
            onClick={handleReset}
            sx={{ color: theme.palette.text.secondary }}
          >
            <ReplayIcon fontSize="small" />
          </IconButton>

          {/* Play/Pause Button */}
          <IconButton
            size="small"
            onClick={handlePlayPause}
            sx={{
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              '&:hover': {
                backgroundColor: theme.palette.primary.dark,
              },
            }}
          >
            {isPlaying ? (
              <PauseIcon fontSize="small" />
            ) : (
              <PlayArrowIcon fontSize="small" />
            )}
          </IconButton>

          {/* Speed Button */}
          <Chip
            label={`${playbackSpeed}x`}
            size="small"
            onClick={handleSpeedChange}
            sx={{
              cursor: 'pointer',
              minWidth: theme.spacing(5),
              '&:hover': {
                backgroundColor: theme.palette.action.hover,
              },
            }}
          />

          {/* Current Time */}
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'monospace',
              minWidth: theme.spacing(8),
              textAlign: 'center',
            }}
          >
            {formatTime(currentTime)}
          </Typography>

          {/* Time Slider */}
          <Slider
            value={currentTime}
            min={timeRange.start}
            max={timeRange.end}
            onChange={handleSliderChange}
            sx={{
              flex: 1,
              mx: theme.spacing(1),
              // Disable transitions to prevent visual "running backwards" when resetting
              '& .MuiSlider-thumb': {
                width: theme.spacing(1.5),
                height: theme.spacing(1.5),
                transition: 'none',
              },
              '& .MuiSlider-track': {
                height: theme.spacing(0.5),
                transition: 'none',
              },
              '& .MuiSlider-rail': {
                height: theme.spacing(0.5),
              },
            }}
          />

          {/* Total Duration */}
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'monospace',
              minWidth: theme.spacing(8),
              textAlign: 'center',
              color: theme.palette.text.secondary,
            }}
          >
            {formatTime(timeRange.end)}
          </Typography>
        </Stack>
      </Paper>

      {/* ReactFlow Container */}
      <Box sx={{ flex: 1, position: 'relative' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          defaultViewport={defaultViewport}
          minZoom={0.1}
          maxZoom={2}
        >
          <Background
            color={theme.palette.divider}
            gap={Number(theme.spacing(2).replace('px', ''))}
          />
          <Controls
            style={{
              display: 'flex',
              flexDirection: 'column',
            }}
          />
          <MiniMap
            nodeColor={node => {
              if (node.hidden) return 'transparent';
              const state = node.data?.state as MarkovState | undefined;
              return state?.type === 'tool'
                ? theme.palette.warning.main
                : theme.palette.info.main;
            }}
            maskColor={
              theme.palette.mode === 'dark'
                ? theme.palette.grey[900] + 'CC' // 80% opacity
                : theme.palette.grey[50] + 'CC' // 80% opacity
            }
            style={{
              backgroundColor: theme.palette.background.paper,
            }}
          />
        </ReactFlow>

        {/* Legend */}
        <Box
          sx={{
            position: 'absolute',
            bottom: theme.spacing(2),
            left: theme.spacing(2),
            backgroundColor: theme.palette.background.paper,
            padding: theme.spacing(1.5),
            borderRadius: theme.spacing(1),
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.shadows[2],
          }}
        >
          <Stack direction="row" spacing={1} sx={{ mb: 0.5 }}>
            <Chip
              icon={<SupportAgentIcon sx={{ fontSize: `${theme.spacing(1.75)} !important` }} />}
              label={`${Array.from(states.values()).filter(s => s.type === 'agent').length} agents`}
              size="small"
              sx={{
                height: theme.spacing(2.5),
                fontSize: theme.typography.caption.fontSize,
                backgroundColor: theme.palette.info.light,
              }}
            />
            <Chip
              icon={<BuildIcon sx={{ fontSize: `${theme.spacing(1.75)} !important` }} />}
              label={`${Array.from(states.values()).filter(s => s.type === 'tool').length} tools`}
              size="small"
              sx={{
                height: theme.spacing(2.5),
                fontSize: theme.typography.caption.fontSize,
                backgroundColor: theme.palette.warning.light,
              }}
            />
          </Stack>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block' }}
          >
            {transitions.length} transitions
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
