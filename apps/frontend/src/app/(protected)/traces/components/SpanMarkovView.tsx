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
  EdgeLabelRenderer,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import SupportAgentIcon from '@mui/icons-material/SupportAgent';

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

// Interface for Markov state (agent)
interface MarkovState {
  id: string;
  name: string;
  invocationCount: number;
  totalDurationMs: number;
  hasError: boolean;
  firstAppearance: number;
}

/**
 * Extract agent states and transitions from spans with timestamps
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
  const agentSequence: { name: string; timestamp: number; spanId: string }[] = [];
  const timedTransitions: TimedTransition[] = [];
  const timedAgentEvents: TimedAgentEvent[] = [];
  let minTime = Infinity;
  let maxTime = -Infinity;

  // Flatten spans and extract agent invocations in order
  function traverse(span: SpanNode) {
    const spanTime = new Date(span.start_time).getTime();
    const spanEndTime = new Date(span.end_time).getTime();
    minTime = Math.min(minTime, spanTime);
    maxTime = Math.max(maxTime, spanEndTime);

    // Check for agent invocations
    if (span.span_name === 'ai.agent.invoke') {
      const agentName = span.attributes?.['ai.agent.name'] as string;
      if (agentName) {
        // Add to sequence for transition tracking
        agentSequence.push({
          name: agentName,
          timestamp: spanTime,
          spanId: span.span_id,
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
          existing.firstAppearance = Math.min(existing.firstAppearance, spanTime);
        } else {
          states.set(agentName, {
            id: agentName,
            name: agentName,
            invocationCount: 1,
            totalDurationMs: span.duration_ms,
            hasError: span.status_code === 'ERROR',
            firstAppearance: spanTime,
          });
        }
      }
    }

    // Check for explicit handoffs
    if (span.span_name === 'ai.agent.handoff') {
      const from = span.attributes?.['ai.agent.handoff.from'] as string;
      const to = span.attributes?.['ai.agent.handoff.to'] as string;
      if (from && to) {
        const key = `${from}->${to}`;
        transitionCounts.set(key, (transitionCounts.get(key) || 0) + 1);

        // Add timed transition
        timedTransitions.push({
          from,
          to,
          timestamp: spanTime,
          spanId: span.span_id,
        });

        // Ensure states exist
        if (!states.has(from)) {
          states.set(from, {
            id: from,
            name: from,
            invocationCount: 0,
            totalDurationMs: 0,
            hasError: false,
            firstAppearance: spanTime,
          });
        }
        if (!states.has(to)) {
          states.set(to, {
            id: to,
            name: to,
            invocationCount: 0,
            totalDurationMs: 0,
            hasError: false,
            firstAppearance: spanTime,
          });
        }
      }
    }

    // Traverse children
    span.children?.forEach(child => traverse(child));
  }

  spans.forEach(span => traverse(span));

  // Sort agent sequence by timestamp
  agentSequence.sort((a, b) => a.timestamp - b.timestamp);

  // Calculate transitions from agent sequence (for self-loops and implicit transitions)
  for (let i = 0; i < agentSequence.length - 1; i++) {
    const current = agentSequence[i];
    const next = agentSequence[i + 1];
    const key = `${current.name}->${next.name}`;

    // Add timed transition if not already from handoff
    const existingTimedTransition = timedTransitions.find(
      t => t.from === current.name && t.to === next.name && t.timestamp === next.timestamp
    );
    if (!existingTimedTransition) {
      timedTransitions.push({
        from: current.name,
        to: next.name,
        timestamp: next.timestamp,
        spanId: next.spanId,
      });
    }

    // Only add to counts if not already counted from handoffs
    if (!transitionCounts.has(key)) {
      transitionCounts.set(key, 1);
    }
  }

  // Also track self-loops from consecutive invocations of the same agent
  let currentAgent = '';
  let currentCount = 0;
  let lastTimestamp = 0;
  let lastSpanId = '';

  for (const agent of agentSequence) {
    if (agent.name === currentAgent) {
      currentCount++;
      // Add self-loop timed transition
      timedTransitions.push({
        from: agent.name,
        to: agent.name,
        timestamp: agent.timestamp,
        spanId: agent.spanId,
      });
    } else {
      if (currentCount > 1) {
        // Record self-loops (count - 1 because first invocation doesn't loop)
        const selfLoopKey = `${currentAgent}->${currentAgent}`;
        transitionCounts.set(
          selfLoopKey,
          (transitionCounts.get(selfLoopKey) || 0) + (currentCount - 1)
        );
      }
      currentAgent = agent.name;
      currentCount = 1;
      lastTimestamp = agent.timestamp;
      lastSpanId = agent.spanId;
    }
  }
  // Handle last group
  if (currentCount > 1) {
    const selfLoopKey = `${currentAgent}->${currentAgent}`;
    transitionCounts.set(
      selfLoopKey,
      (transitionCounts.get(selfLoopKey) || 0) + (currentCount - 1)
    );
  }

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
 * Calculate transition probabilities
 */
function calculateProbabilities(
  transitions: StateTransition[]
): Map<string, number> {
  const probabilities = new Map<string, number>();
  const outgoingCounts = new Map<string, number>();

  // Sum up outgoing transitions for each state
  transitions.forEach(t => {
    outgoingCounts.set(t.from, (outgoingCounts.get(t.from) || 0) + t.count);
  });

  // Calculate probabilities
  transitions.forEach(t => {
    const total = outgoingCounts.get(t.from) || 1;
    const prob = t.count / total;
    probabilities.set(`${t.from}->${t.to}`, prob);
  });

  return probabilities;
}

/**
 * Custom node component for Markov states (agents)
 */
function MarkovStateNode({ data }: NodeProps) {
  const theme = useTheme();
  const { state, isSelected } = data as {
    state: MarkovState;
    isSelected: boolean;
  };

  const avgDuration =
    state.invocationCount > 0
      ? state.totalDurationMs / state.invocationCount
      : 0;

  const formatDuration = (ms: number) => {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <Box
      sx={{
        padding: theme.spacing(2),
        borderRadius: theme.spacing(1),
        backgroundColor: theme.palette.background.paper,
        border: `3px solid ${isSelected ? theme.palette.primary.main : theme.palette.info.main}`,
        boxShadow: isSelected
          ? `0 0 0 3px ${theme.palette.primary.light}`
          : theme.shadows[2],
        minWidth: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        cursor: 'pointer',
        transition: theme.transitions.create(['border-color', 'box-shadow']),
        '&:hover': {
          borderColor: theme.palette.primary.light,
          boxShadow: theme.shadows[4],
        },
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: theme.spacing(0.5),
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: theme.palette.info.main,
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
          background: theme.palette.info.main,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />

      {/* Agent Icon */}
      <SupportAgentIcon
        sx={{
          fontSize: theme.spacing(3),
          color: state.hasError
            ? theme.palette.error.main
            : theme.palette.info.main,
        }}
      />

      {/* State Name */}
      <Typography
        variant="subtitle2"
        sx={{
          fontWeight: theme.typography.fontWeightBold,
          textAlign: 'center',
          color: state.hasError
            ? theme.palette.error.main
            : theme.palette.text.primary,
        }}
      >
        {state.name}
      </Typography>

      {/* Stats */}
      <Box
        sx={{ display: 'flex', gap: theme.spacing(0.5), flexWrap: 'wrap', justifyContent: 'center' }}
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

      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: theme.palette.info.main,
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
          background: theme.palette.info.main,
          border: 'none',
          width: theme.spacing(1.5),
          height: theme.spacing(1.5),
        }}
      />
    </Box>
  );
}

/**
 * Custom edge component with probability label
 */
function ProbabilityEdge({
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
  const theme = useTheme();
  const { probability, count, isSelfLoop, selfLoopIndex, selfLoopTotal } = data as {
    probability: number;
    count: number;
    isSelfLoop: boolean;
    selfLoopIndex?: number;
    selfLoopTotal?: number;
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

    // Only show label on the last (outermost) self-loop
    const showLabel = selfLoopTotal === undefined || index === selfLoopTotal - 1;

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
        {showLabel && (
          <EdgeLabelRenderer>
            <Box
              sx={{
                position: 'absolute',
                transform: `translate(-50%, -50%) translate(${sourceX + loopRadius * 1.5}px, ${sourceY}px)`,
                backgroundColor: theme.palette.background.paper,
                padding: theme.spacing(0.25, 0.75),
                borderRadius: theme.spacing(0.5),
                fontSize: theme.typography.caption.fontSize,
                fontWeight: theme.typography.fontWeightMedium,
                border: `1px solid ${theme.palette.divider}`,
                pointerEvents: 'all',
                cursor: 'pointer',
              }}
            >
              {(probability * 100).toFixed(0)}% ({count})
            </Box>
          </EdgeLabelRenderer>
        )}
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
      <EdgeLabelRenderer>
        <Box
          sx={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            backgroundColor: theme.palette.background.paper,
            padding: theme.spacing(0.25, 0.75),
            borderRadius: theme.spacing(0.5),
            fontSize: theme.typography.caption.fontSize,
            fontWeight: theme.typography.fontWeightMedium,
            border: `1px solid ${theme.palette.divider}`,
            pointerEvents: 'all',
            cursor: 'pointer',
          }}
        >
          {(probability * 100).toFixed(0)}% ({count})
        </Box>
      </EdgeLabelRenderer>
    </>
  );
}

// Define custom node and edge types
const nodeTypes = {
  markovState: MarkovStateNode,
};

const edgeTypes = {
  probability: ProbabilityEdge,
};

/**
 * Convert Markov chain to ReactFlow elements
 */
function convertToFlowElements(
  states: Map<string, MarkovState>,
  transitions: StateTransition[],
  probabilities: Map<string, number>,
  edgeColor: string
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
    const prob = probabilities.get(`${t.from}->${t.to}`) || 0;

    if (isSelfLoop && t.count > 1) {
      // Create multiple self-loop edges with different offsets
      for (let i = 0; i < t.count; i++) {
        edges.push({
          id: `${t.from}->${t.to}-${i}`,
          source: t.from,
          target: t.to,
          type: 'probability',
          sourceHandle: 'right',
          targetHandle: 'left',
          data: {
            probability: prob,
            count: t.count,
            isSelfLoop: true,
            selfLoopIndex: i,
            selfLoopTotal: t.count,
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
        type: 'probability',
        sourceHandle: isSelfLoop ? 'right' : undefined,
        targetHandle: isSelfLoop ? 'left' : undefined,
        data: {
          probability: prob,
          count: t.count,
          isSelfLoop,
          selfLoopIndex: 0,
          selfLoopTotal: 1,
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

/**
 * Apply dagre layout to position nodes
 */
function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  if (nodes.length === 0) return nodes;

  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: 'LR', // Left to right for Markov chains
    align: 'UL',
    ranker: 'network-simplex',
    nodesep: 100,
    ranksep: 150,
    edgesep: 50,
    marginx: 50,
    marginy: 50,
  });

  nodes.forEach(node => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
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
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
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

  // Extract Markov chain from spans with time data
  const {
    states,
    transitions,
    probabilities,
    initialNodes,
    initialEdges,
    timedTransitions,
    timedAgentEvents,
    timeRange,
  } = useMemo(() => {
    const {
      states,
      transitions,
      timedTransitions,
      timedAgentEvents,
      timeRange,
    } = extractMarkovChain(spans);
    const probabilities = calculateProbabilities(transitions);
    const edgeColor = theme.palette.info.main;
    const { nodes, edges } = convertToFlowElements(
      states,
      transitions,
      probabilities,
      edgeColor
    );
    const layoutedNodes = applyDagreLayout(nodes, edges);
    return {
      states,
      transitions,
      probabilities,
      initialNodes: layoutedNodes,
      initialEdges: edges,
      timedTransitions,
      timedAgentEvents,
      timeRange,
    };
  }, [spans, theme.palette.info.main]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Time slider state
  const [currentTime, setCurrentTime] = useState(timeRange.end);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const animationRef = useRef<number | null>(null);
  const lastFrameTime = useRef<number>(0);

  // Duration of the trace in ms
  const traceDuration = timeRange.end - timeRange.start;

  // Reset to start when spans change
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

    // Find which transitions have occurred by current time
    const transitionCounts = new Map<string, number>();
    timedTransitions.forEach(t => {
      if (t.timestamp <= currentTime) {
        const key = `${t.from}->${t.to}`;
        transitionCounts.set(key, (transitionCounts.get(key) || 0) + 1);
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
        const baseKey = edge.source === edge.target
          ? `${edge.source}->${edge.target}`
          : `${edge.source}->${edge.target}`;
        const count = transitionCounts.get(baseKey) || 0;

        // For self-loops, show based on index
        if (edge.data?.isSelfLoop && edge.data?.selfLoopIndex !== undefined) {
          const shouldShow = edge.data.selfLoopIndex < count;
          return {
            ...edge,
            hidden: !shouldShow,
            animated: shouldShow && edge.data.selfLoopIndex === count - 1,
            style: {
              ...edge.style,
              opacity: shouldShow ? 1 : 0,
            },
          };
        }

        // For regular edges
        const shouldShow = count > 0;
        return {
          ...edge,
          hidden: !shouldShow,
          animated: shouldShow,
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
    if (currentTime >= timeRange.end) {
      setCurrentTime(timeRange.start);
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

  // Handle node click - find an agent span with this name
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const agentName = node.id;
      // Find first agent span with this name
      function findAgentSpan(spans: SpanNode[]): SpanNode | null {
        for (const span of spans) {
          if (
            span.span_name === 'ai.agent.invoke' &&
            span.attributes?.['ai.agent.name'] === agentName
          ) {
            return span;
          }
          if (span.children) {
            const found = findAgentSpan(span.children);
            if (found) return found;
          }
        }
        return null;
      }
      const agentSpan = findAgentSpan(spans);
      if (agentSpan) {
        onSpanSelect(agentSpan);
      }
    },
    [spans, onSpanSelect]
  );

  // Handle edge click - find the corresponding handoff or agent span
  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const sourceAgent = edge.source;
      const targetAgent = edge.target;
      const isSelfLoop = sourceAgent === targetAgent;

      function findSpan(spans: SpanNode[]): SpanNode | null {
        for (const span of spans) {
          // For transitions between different agents, look for handoff spans
          if (!isSelfLoop && span.span_name === 'ai.agent.handoff') {
            const from = span.attributes?.['ai.agent.handoff.from'];
            const to = span.attributes?.['ai.agent.handoff.to'];
            if (from === sourceAgent && to === targetAgent) {
              return span;
            }
          }

          // For self-loops, find the target agent's invoke span
          if (isSelfLoop && span.span_name === 'ai.agent.invoke') {
            const agentName = span.attributes?.['ai.agent.name'];
            if (agentName === targetAgent) {
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
          Markov view requires ai.agent.invoke spans
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        minHeight: 400,
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
          zIndex: 10,
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
              '& .MuiSlider-thumb': {
                width: theme.spacing(1.5),
                height: theme.spacing(1.5),
              },
              '& .MuiSlider-track': {
                height: theme.spacing(0.5),
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
          fitView
          fitViewOptions={{ padding: 0.3 }}
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
            nodeColor={node =>
              node.hidden ? 'transparent' : theme.palette.info.main
            }
            maskColor={
              theme.palette.mode === 'dark'
                ? 'rgba(0,0,0,0.8)'
                : 'rgba(255,255,255,0.8)'
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
          <Typography
            variant="caption"
            sx={{
              fontWeight: theme.typography.fontWeightBold,
              display: 'block',
              mb: 0.5,
            }}
          >
            Markov Chain
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block' }}
          >
            States: {states.size} agents
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block' }}
          >
            Transitions: {transitions.length}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}
          >
            Edge labels show probability (count)
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
