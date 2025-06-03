'use client';

import * as React from 'react';
import { Box, Paper, Typography, Tabs, Tab, Chip, Breadcrumbs, TextField, Button, CircularProgress } from '@mui/material';
import Link from 'next/link';
import EditableTable from '../wizard/components/EditableTable';
import { Project } from '@/utils/api-client/interfaces/project';
import ProjectSankey from './ProjectSankey';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import PromptsTable from './PromptsTable';
import { Edge, Node } from 'reactflow';
import { generatePrompts } from './PromptsTable';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      {...other}
    >
      {value === index && (
        <Box sx={{ py: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

interface ProjectDetailsProps {
  project: Project;
  sessionToken: string;
}

export default function ProjectDetails({ project: initialProject, sessionToken }: ProjectDetailsProps) {
  const [project, setProject] = React.useState<Project>(initialProject);
  const [tabValue, setTabValue] = React.useState(0);
  const [edges, setEdges] = React.useState<Edge[]>([]);
  const [nodes, setNodes] = React.useState<Node[]>([]);
  const [completePaths, setCompletePaths] = React.useState<any[]>([]);
  const [isGeneratingPrompts, setIsGeneratingPrompts] = React.useState(false);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleGeneratePrompts = async () => {
    setIsGeneratingPrompts(true);
    setCompletePaths([]);
    
    // Call generate prompts directly instead of relying on tab change
    const result = await generatePrompts(edges, nodes, project.requirements || [], project.scenarios || [], project.personas || [], sessionToken);
    if (result.length > 0) {
      setCompletePaths(result);
      setTabValue(7); // Only switch tab after successful generation
    }
    setIsGeneratingPrompts(false);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <div>
          <Breadcrumbs>
            <Link href="/projects-legacy" style={{ textDecoration: 'none', color: 'inherit' }}>
              Projects
            </Link>
            <Typography color="text.primary">{project.name}</Typography>
          </Breadcrumbs>
          <Typography variant="h4" sx={{ mt: 1, mb: 2 }}>
            {project.name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {project.tags?.map((tag) => (
              <Chip
                key={tag}
                label={tag}
                sx={{
                  '& .MuiChip-deleteIcon': {
                    display: 'none'
                  },
                  '&:hover .MuiChip-deleteIcon': {
                    display: 'block'
                  }
                }}
                onDelete={() => {
                  setProject({
                    ...project,
                    tags: project.tags?.filter(t => t !== tag) || []
                  });
                }}
              />
            ))}
            <Chip
              label="+ Add Tag"
              variant="outlined"
              onClick={() => {
                const newTag = prompt('Enter new tag:');
                if (newTag && project.tags) {
                  if (!project.tags.includes(newTag)) {
                    setProject({
                      ...project,
                      tags: [...project.tags, newTag]
                    });
                  }
                } else if (newTag) {
                  setProject({
                    ...project,
                    tags: [newTag]
                  });
                }
              }}
            />
          </Box>
        </div>
        <Chip 
          label={project.environment}
          color={project.environment === 'production' ? 'success' : project.environment === 'staging' ? 'warning' : 'info'}
          variant="outlined"
        />
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} sx={{ px: 2, pt: 2 }}>
          <Tab label="Overview" />
          <Tab label="Goals & Capabilities" />
          <Tab label="Agents" />
          <Tab label="Requirements" />
          <Tab label="Scenarios" />
          <Tab label="Personas" />
          <Tab label="Flow" />
          <Tab label="Combinations" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <Box sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Project Details
            </Typography>
            <TextField
              fullWidth
              label="Name"
              value={project.name}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Description"
              value={project.description}
              multiline
              rows={3}
              sx={{ mb: 2 }}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <Box sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Primary Goals
            </Typography>
            <EditableTable
              data={project.system?.primary_goals.map((goal, index) => ({
                id: `goal-${index}`,
                name: goal
              })) || []}
              columns={[
                { id: 'name', label: 'Goal' }
              ]}
              onUpdate={(goals) => {
                setProject({
                  ...project,
                  system: {
                    ...project.system!,
                    primary_goals: goals.map(g => g.name)
                  }
                });
              }}
            />

            <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
              Key Capabilities
            </Typography>
            <EditableTable
              data={project.system?.key_capabilities.map((capability, index) => ({
                id: `capability-${index}`,
                name: capability
              })) || []}
              columns={[
                { id: 'name', label: 'Capability' }
              ]}
              onUpdate={(capabilities) => {
                setProject({
                  ...project,
                  system: {
                    ...project.system!,
                    key_capabilities: capabilities.map(c => c.name)
                  }
                });
              }}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <Box sx={{ p: 2 }}>
            <EditableTable
              data={project.agents || []}
              columns={[
                { id: 'name', label: 'Name' },
                { id: 'description', label: 'Description' },
              ]}
              onUpdate={() => {}}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <Box sx={{ p: 2 }}>
            <EditableTable
              data={project.requirements || []}
              columns={[
                { id: 'name', label: 'Requirement' },
                { id: 'description', label: 'Description' },
              ]}
              onUpdate={() => {}}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={4}>
          <Box sx={{ p: 2 }}>
            <EditableTable
              data={project.scenarios || []}
              columns={[
                { id: 'name', label: 'Scenario' },
                { id: 'description', label: 'Description' },
              ]}
              onUpdate={() => {}}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={5}>
          <Box sx={{ p: 2 }}>
            <EditableTable
              data={project.personas || []}
              columns={[
                { id: 'name', label: 'Persona' },
                { id: 'description', label: 'Description' },
              ]}
              onUpdate={() => {}}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={6}>
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <div>
                <Typography variant="h6" gutterBottom>
                  Requirements Flow
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Visualize and manage connections between requirements, scenarios, and personas.
                </Typography>
              </div>
              <Button
                variant="contained"
                color="primary"
                onClick={handleGeneratePrompts}
                startIcon={isGeneratingPrompts ? <CircularProgress size={20} color="inherit" /> : <AutoAwesome />}
                disabled={isGeneratingPrompts || !edges.some(edge => {
                  // Find all edges that connect to this edge's target
                  const connectedEdges = edges.filter(e => e.source === edge.target);
                  // Check if any of these edges connect to a persona
                  return connectedEdges.some(e => {
                    const targetNode = nodes.find(n => n.id === e.target);
                    return targetNode?.type === 'persona';
                  });
                })}
              >
                {isGeneratingPrompts ? 'Generating...' : 'Generate Combinations'}
              </Button>
            </Box>
            <ProjectSankey
              requirements={project.requirements || []}
              scenarios={project.scenarios || []}
              personas={project.personas || []}
              onEdgesChange={setEdges}
              onNodesChange={setNodes}
              initialEdges={edges}
            />
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={7}>
          <Box sx={{ p: 2 }}>
            <PromptsTable
              edges={edges}
              nodes={nodes}
              requirements={project.requirements || []}
              scenarios={project.scenarios || []}
              personas={project.personas || []}
              sessionToken={sessionToken}
              completePaths={completePaths}
              setCompletePaths={setCompletePaths}
              setIsGenerating={setIsGeneratingPrompts}
            />
          </Box>
        </TabPanel>
      </Paper>
    </Box>
  );
} 