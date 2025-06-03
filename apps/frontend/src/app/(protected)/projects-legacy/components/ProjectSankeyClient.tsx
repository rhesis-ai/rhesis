'use client';

import React, { useCallback, useMemo, useEffect, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Handle,
  Position,
  EdgeProps,
  getBezierPath,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Box, Typography, Paper, IconButton, Tooltip } from '@mui/material';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import PersonIcon from '@mui/icons-material/Person';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import NodeEditDialog from './NodeEditDialog';
import PathDetailsPanel from './PathDetailsPanel';
import InfoIcon from '@mui/icons-material/Info';

interface ProjectSankeyProps {
  requirements: Array<{ name: string; description: string }>;
  scenarios: Array<{ name: string; description: string }>;
  personas: Array<{ name: string; description: string }>;
  onEdgesChange: (edges: Edge[]) => void;
  onNodesChange: (nodes: Node[]) => void;
  initialEdges?: Edge[];
}

// Add hover state management to each node component
const NodeControls = ({ onEdit, onDelete, visible, color }: { 
  onEdit: () => void, 
  onDelete: () => void, 
  visible: boolean,
  color: string 
}) => (
  <Box
    sx={{
      position: 'absolute',
      right: '8px',
      top: 0,
      bottom: 0,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-around',
      opacity: visible ? 1 : 0,
      transition: 'opacity 0.2s ease-in-out',
      pointerEvents: visible ? 'auto' : 'none',
    }}
  >
    <Box
      sx={{
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        bgcolor: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        '&:hover': {
          filter: 'brightness(0.9)',
        }
      }}
      onClick={(e) => {
        e.stopPropagation();
        onEdit();
      }}
    >
      <EditIcon sx={{ fontSize: 8, color: 'white' }} />
    </Box>
    <Box
      sx={{
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        bgcolor: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        '&:hover': {
          filter: 'brightness(0.9)',
        }
      }}
      onClick={(e) => {
        e.stopPropagation();
        onDelete();
      }}
    >
      <DeleteIcon sx={{ fontSize: 8, color: 'white' }} />
    </Box>
  </Box>
);

const RequirementNode = ({ data, id }: any) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const color = '#ffb74d';

  return (
    <Box
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{ position: 'relative' }}
    >
      <Paper 
        elevation={2}
        sx={{
          p: 1.5,
          bgcolor: '#fff3e0',
          borderRadius: 2,
          width: 200,
          border: `2px solid ${color}`,
        }}
      >
        <Handle type="source" position={Position.Right} style={{ background: color }} />
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AssignmentIcon sx={{ color: '#f57c00' }} />
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ color: '#e65100' }}>Requirement</Typography>
            <Typography variant="body2">{data.label}</Typography>
          </Box>
        </Box>
      </Paper>
      <NodeControls
        onEdit={() => data.onEdit(id)}
        onDelete={() => data.onDelete(id)}
        visible={isHovered}
        color={color}
      />
    </Box>
  );
};

const ScenarioNode = ({ data, id }: any) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const color = '#64b5f6';

  return (
    <Box
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{ position: 'relative' }}
    >
      <Paper 
        elevation={2}
        sx={{
          p: 1.5,
          bgcolor: '#e3f2fd',
          borderRadius: 2,
          width: 200,
          border: `2px solid ${color}`,
        }}
      >
        <Handle type="target" position={Position.Left} style={{ background: color }} />
        <Handle type="source" position={Position.Right} style={{ background: color }} />
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AccountTreeIcon sx={{ color: '#1976d2' }} />
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ color: '#0d47a1' }}>Scenario</Typography>
            <Typography variant="body2">{data.label}</Typography>
          </Box>
        </Box>
      </Paper>
      <NodeControls
        onEdit={() => data.onEdit(id)}
        onDelete={() => data.onDelete(id)}
        visible={isHovered}
        color={color}
      />
    </Box>
  );
};

const PersonaNode = ({ data, id }: any) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const color = '#81c784';

  return (
    <Box
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{ position: 'relative' }}
    >
      <Paper 
        elevation={2}
        sx={{
          p: 1.5,
          bgcolor: '#e8f5e9',
          borderRadius: 2,
          width: 200,
          border: `2px solid ${color}`,
        }}
      >
        <Handle type="target" position={Position.Left} style={{ background: color }} />
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <PersonIcon sx={{ color: '#388e3c' }} />
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" sx={{ color: '#1b5e20' }}>Persona</Typography>
            <Typography variant="body2">{data.label}</Typography>
          </Box>
        </Box>
      </Paper>
      <NodeControls
        onEdit={() => data.onEdit(id)}
        onDelete={() => data.onDelete(id)}
        visible={isHovered}
        color={color}
      />
    </Box>
  );
};

const nodeTypes = {
  requirement: RequirementNode,
  scenario: ScenarioNode,
  persona: PersonaNode,
};

// Add helper function to determine if a node is part of a complete path
function isPartOfCompletePath(
  edge: Edge,
  edges: Edge[],
  nodes: Node[]
): boolean {
  // Get node types for the current edge
  const sourceNode = nodes.find(n => n.id === edge.source);
  const targetNode = nodes.find(n => n.id === edge.target);
  
  if (!sourceNode || !targetNode) return false;

  // If this is a requirement -> scenario connection
  if (sourceNode.type === 'requirement' && targetNode.type === 'scenario') {
    // Check if this scenario connects to any persona
    return edges.some(e => 
      e.source === edge.target && 
      nodes.find(n => n.id === e.target)?.type === 'persona'
    );
  }

  // If this is a scenario -> persona connection
  if (sourceNode.type === 'scenario' && targetNode.type === 'persona') {
    // Check if this scenario is connected to any requirement
    return edges.some(e => 
      e.target === edge.source && 
      nodes.find(n => n.id === e.source)?.type === 'requirement'
    );
  }

  return false;
}

export default function ProjectSankey({ 
  requirements, 
  scenarios, 
  personas, 
  onEdgesChange: onEdgesUpdate,
  onNodesChange: onNodesUpdate,
  initialEdges = [],
}: ProjectSankeyProps) {
  const [editDialog, setEditDialog] = React.useState({
    open: false,
    type: '',
    data: { name: '', description: '' },
    id: ''
  });

  const [selectedPathEdges, setSelectedPathEdges] = React.useState<string[]>([]);
  const [pathDetails, setPathDetails] = React.useState<{
    open: boolean;
    requirement?: any;
    scenario?: any;
    persona?: any;
    edgeId?: string;
  }>({
    open: false
  });

  const handleEdit = (type: string, id: string) => {
    const items = type === 'requirement' ? requirements :
                 type === 'scenario' ? scenarios :
                 personas;
    const item = items.find((_, index) => `${type}-${index}` === id);
    if (item) {
      setEditDialog({
        open: true,
        type,
        data: item,
        id
      });
    }
  };

  const handleDelete = (id: string) => {
    setNodes(nodes.filter(node => node.id !== id));
    setEdges(edges.filter(edge => edge.source !== id && edge.target !== id));
  };

  const handleSave = (data: { name: string; description: string }) => {
    setNodes(nodes.map(node => 
      node.id === editDialog.id 
        ? { ...node, data: { ...node.data, label: data.name } }
        : node
    ));
  };

  // Create initial nodes with more spacing
  const initialNodes: Node[] = [
    // Requirements column
    ...requirements.map((req, index) => ({
      id: `requirement-${index}`,
      type: 'requirement',
      data: { 
        label: req.name,
        onEdit: (id: string) => handleEdit('requirement', id),
        onDelete: handleDelete
      },
      position: { x: 100, y: index * 150 + 50 },
      draggable: true,
    })),
    // Scenarios column
    ...scenarios.map((scenario, index) => ({
      id: `scenario-${index}`,
      type: 'scenario',
      data: { 
        label: scenario.name,
        onEdit: (id: string) => handleEdit('scenario', id),
        onDelete: handleDelete
      },
      position: { x: 450, y: index * 150 + 50 },
      draggable: true,
    })),
    // Personas column
    ...personas.map((persona, index) => ({
      id: `persona-${index}`,
      type: 'persona',
      data: { 
        label: persona.name,
        onEdit: (id: string) => handleEdit('persona', id),
        onDelete: handleDelete
      },
      position: { x: 800, y: index * 150 + 50 },
      draggable: true,
    })),
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // CustomEdge definition with glow effect
  const CustomEdge = useCallback(({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    data,
  }: EdgeProps) => {
    const [edgePath] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
    });

    const isHovered = data?.isHovered || false;
    const foreignObjectSize = 40;
    const centerX = (sourceX + targetX) / 2;
    const centerY = (sourceY + targetY) / 2;

    const edgeStyle = {
      ...style,
      stroke: data?.isCompletePath ? '#f57c00' : '#b1b1b7',
      strokeWidth: data?.isCompletePath ? 3 : 1,
      strokeDasharray: data?.isCompletePath ? 'none' : '5,5',
    };

    return (
      <>
        <path
          id={id}
          style={edgeStyle}
          className="react-flow__edge-path"
          d={edgePath}
          markerEnd={markerEnd}
          onMouseEnter={() => {
            data?.onHover?.(id, true);
          }}
          onMouseLeave={() => {
            data?.onHover?.(id, false);
          }}
        />
        {isHovered && (
          <foreignObject
            width={foreignObjectSize}
            height={foreignObjectSize}
            x={centerX - foreignObjectSize / 2}
            y={centerY - foreignObjectSize / 2}
            className="edgebutton-foreignobject"
            requiredExtensions="http://www.w3.org/1999/xhtml"
          >
            <div
              style={{
                background: '#fff',
                width: foreignObjectSize,
                height: foreignObjectSize,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                borderRadius: '50%',
                border: '1px solid #eee',
              }}
            >
              <InfoIcon style={{ fontSize: 20, color: '#666' }} />
            </div>
          </foreignObject>
        )}
      </>
    );
  }, []);

  // Update edge types with memoized custom edge
  const edgeTypes = useMemo(() => ({
    custom: CustomEdge,
  }), [CustomEdge]);

  // Update edges with completion status
  const updateEdgesWithCompletionStatus = useCallback((newEdges: Edge[]) => {
    return newEdges.map(edge => ({
      ...edge,
      data: {
        ...edge.data,
        isCompletePath: isPartOfCompletePath(edge, newEdges, nodes)
      }
    }));
  }, [nodes]);

  // Modified onConnect handler
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => {
        const newEdges = addEdge({
          ...params,
          animated: true,
          type: 'custom',
        }, eds);
        return updateEdgesWithCompletionStatus(newEdges);
      });
    },
    [setEdges, updateEdgesWithCompletionStatus]
  );

  // Modified edge click handler
  const onEdgeClick = useCallback(
    (evt: React.MouseEvent, edge: Edge) => {
      // Helper function moved inside the callback
      const getCompletePath = (edge: Edge) => {
        if (!isPartOfCompletePath(edge, edges, nodes)) return null;

        const sourceNode = nodes.find(n => n.id === edge.source);
        const targetNode = nodes.find(n => n.id === edge.target);
        
        if (!sourceNode || !targetNode) return null;

        let requirement, scenario, persona;

        if (sourceNode.type === 'requirement') {
          requirement = requirements.find((_, i) => `requirement-${i}` === sourceNode.id);
          scenario = scenarios.find((_, i) => `scenario-${i}` === targetNode.id);
          // Find connected persona
          const personaEdge = edges.find(e => e.source === targetNode.id);
          if (personaEdge) {
            persona = personas.find((_, i) => `persona-${i}` === personaEdge.target);
          }
        } else {
          persona = personas.find((_, i) => `persona-${i}` === targetNode.id);
          scenario = scenarios.find((_, i) => `scenario-${i}` === sourceNode.id);
          // Find connected requirement
          const requirementEdge = edges.find(e => e.target === sourceNode.id);
          if (requirementEdge) {
            requirement = requirements.find((_, i) => `requirement-${i}` === requirementEdge.source);
          }
        }

        return { requirement, scenario, persona };
      };

      const target = evt.target as HTMLElement;
      if (target.classList.contains('edge-delete-button')) {
        setEdges((eds) => {
          const newEdges = eds.filter((e) => e.id !== edge.id);
          return updateEdgesWithCompletionStatus(newEdges);
        });
        setSelectedPathEdges([]);
        return;
      }

      // Show path details if it's a complete path
      const pathData = getCompletePath(edge);
      if (pathData?.scenario?.name) {
        const scenarioId = nodes.find(n => n.data.label === (pathData.scenario as { name: string }).name)?.id;
        const pathEdges = edges.filter(e => 
          (e.source === scenarioId || e.target === scenarioId)
        ).map(e => e.id);
        
        setSelectedPathEdges(pathEdges);
        setPathDetails({
          open: true,
          ...pathData
        });
      }
    },
    [edges, nodes, requirements, scenarios, personas, setEdges, updateEdgesWithCompletionStatus]
  );

  // Modified context menu handler
  const onEdgeContextMenu = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      event.preventDefault(); // Prevent default context menu
      setEdges((eds) => {
        const newEdges = eds.filter((e) => e.id !== edge.id);
        return updateEdgesWithCompletionStatus(newEdges);
      });
      // Clear any selected edges if they exist
      setSelectedPathEdges([]);
    },
    [setEdges, updateEdgesWithCompletionStatus]
  );

  const handlePanelClose = useCallback(() => {
    setPathDetails({ open: false });
    setSelectedPathEdges([]);
  }, []);

  useEffect(() => {
    setEdges(edges => edges.map(edge => ({
      ...edge,
      data: { 
        ...edge.data, 
        isSelected: selectedPathEdges.includes(edge.id)
      }
    })));
  }, [selectedPathEdges, setEdges]);

  // Add effect to propagate changes
  useEffect(() => {
    onEdgesUpdate(edges);
  }, [edges, onEdgesUpdate]);

  useEffect(() => {
    onNodesUpdate(nodes);
  }, [nodes, onNodesUpdate]);

  return (
    <Box sx={{ height: 500, width: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onEdgeClick={onEdgeClick}
        onEdgeContextMenu={onEdgeContextMenu}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        defaultViewport={{ x: 0, y: 0, zoom: 1.2 }}
        defaultEdgeOptions={{
          type: 'custom',
          animated: false,
        }}
      >
        <Background />
        <Controls />
        <MiniMap 
          nodeColor={(node) => {
            switch (node.type) {
              case 'requirement':
                return '#ffb74d';
              case 'scenario':
                return '#64b5f6';
              case 'persona':
                return '#81c784';
              default:
                return '#eee';
            }
          }}
        />
      </ReactFlow>
      <Box sx={{ mt: 2, p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Connect elements by dragging from the right handle of a node to the left handle of another node.
          Remove connections by right-clicking them or using the delete button that appears when hovering over a connection.
          Orange connections indicate complete paths from requirements through scenarios to personas.
        </Typography>
      </Box>
      
      <NodeEditDialog
        open={editDialog.open}
        onClose={() => setEditDialog({ ...editDialog, open: false })}
        onSave={handleSave}
        data={editDialog.data}
        title={editDialog.type.charAt(0).toUpperCase() + editDialog.type.slice(1)}
      />
      <PathDetailsPanel
        open={pathDetails.open}
        onClose={handlePanelClose}
        requirement={pathDetails.requirement}
        scenario={pathDetails.scenario}
        persona={pathDetails.persona}
      />
    </Box>
  );
} 