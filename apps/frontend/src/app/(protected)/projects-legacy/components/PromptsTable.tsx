import React, { useEffect, useState, useMemo } from 'react';
import { Typography, Box, CircularProgress, IconButton, TextField, MenuItem, Button, TablePagination } from '@mui/material';
import { Edge, Node as FlowNode } from 'reactflow';
import BaseTable from '@/components/common/BaseTable';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import generatePromptTemplate from '../templates/generate_prompt.md';
import EditIcon from '@mui/icons-material/Edit';
import EditPromptDialog from './EditPromptDialog';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ScienceIcon from '@mui/icons-material/Science';
import TestsDialog from './TestsDialog';
import generateTestsTemplate from '../templates/generate_tests.md';
import { Test } from '../types/test';

interface PromptsTableProps {
  edges: Edge[];
  nodes: FlowNode[];
  requirements: Array<{ name: string; description: string }>;
  scenarios: Array<{ name: string; description: string }>;
  personas: Array<{ name: string; description: string }>;
  sessionToken: string;
  completePaths: any[];
  setCompletePaths: (paths: any[]) => void;
  setIsGenerating: (isGenerating: boolean) => void;
  setTabValue?: React.Dispatch<React.SetStateAction<number>>;
}

// Export the generate function to be used by parent
export const generatePrompts = async (
  edges: Edge[],
  nodes: FlowNode[],
  requirements: Array<{ name: string; description: string }>,
  scenarios: Array<{ name: string; description: string }>,
  personas: Array<{ name: string; description: string }>,
  sessionToken: string
) => {
  const client = new ApiClientFactory(sessionToken).getServicesClient();

  try {
    // Find all requirement-scenario connections
    const reqScenarioPaths = edges.reduce((paths: any[], edge) => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      
      if (!sourceNode || !targetNode) return paths;

      // Check for requirement -> scenario connection
      if (sourceNode.type === 'requirement' && targetNode.type === 'scenario') {
        const requirement = requirements.find((_, i) => `requirement-${i}` === sourceNode.id);
        const scenario = scenarios.find((_, i) => `scenario-${i}` === targetNode.id);
        
        if (requirement && scenario) {
          paths.push({ requirement, scenario, scenarioId: targetNode.id });
        }
      }
      return paths;
    }, []);

    // Find all scenario-persona connections and combine with requirement paths
    const completePaths = reqScenarioPaths.reduce((allPaths: any[], reqPath) => {
      const scenarioPersonaEdges = edges.filter(edge => 
        edge.source === reqPath.scenarioId && 
        nodes.find(n => n.id === edge.target)?.type === 'persona'
      );

      // For each persona connected to this scenario, create a complete path
      scenarioPersonaEdges.forEach(edge => {
        const persona = personas.find((_, i) => `persona-${i}` === edge.target);
        if (persona) {
          allPaths.push({
            requirement: reqPath.requirement,
            scenario: reqPath.scenario,
            persona: persona
          });
        }
      });

      return allPaths;
    }, []);

    // Create all prompts in parallel
    const promptPromises = completePaths.map(async (path) => {
      if (!path.requirement?.name || !path.scenario?.name || !path.persona?.name) {
        console.error('Invalid path data:', path);
        return null;
      }

      const prompt = generatePromptTemplate
        .replace('{requirement}', `${path.requirement.name}: ${path.requirement.description || ''}`)
        .replace('{scenario}', `${path.scenario.name}: ${path.scenario.description || ''}`)
        .replace('{persona}', `${path.persona.name}: ${path.persona.description || ''}`);

      try {
        const response = await client.getOpenAIChat([
          { role: 'system', content: 'You are a helpful assistant that generates test prompts.' },
          { role: 'user', content: prompt }
        ]);
        return { ...path, prompt: response };
      } catch (error) {
        console.error('Error generating prompt:', error);
        return null;
      }
    });

    // Wait for all prompts to be generated
    const results = await Promise.all(promptPromises);
    return results.filter(Boolean);

  } catch (error) {
    console.error('Error generating prompts:', error);
    return [];
  }
};

export default function PromptsTable({ 
  edges, 
  nodes, 
  requirements, 
  scenarios, 
  personas, 
  sessionToken,
  completePaths,
  setCompletePaths,
  setIsGenerating,
  setTabValue = () => {}
}: PromptsTableProps) {
  const [editDialog, setEditDialog] = React.useState({
    open: false,
    prompt: '',
    index: -1,
    requirement: { name: '', description: '' },
    scenario: { name: '', description: '' },
    persona: { name: '', description: '' },
  });

  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    requirement: '',
    scenario: '',
    persona: '',
  });

  const [testsDialog, setTestsDialog] = React.useState({
    open: false,
    tests: [] as Test[],
    isLoading: false,
    prompt: '',
  });

  const handleEdit = (row: any, index: number) => {
    setEditDialog({
      open: true,
      prompt: row.prompt,
      index,
      requirement: row.requirement,
      scenario: row.scenario,
      persona: row.persona,
    });
  };

  const handleSavePrompt = (newPrompt: string) => {
    const newPaths = [...completePaths];
    newPaths[editDialog.index] = {
      ...newPaths[editDialog.index],
      prompt: newPrompt,
    };
    setCompletePaths(newPaths);
  };

  const handleGenerateTests = async (row: any) => {
    setTestsDialog({
      open: true,
      tests: [],
      isLoading: true,
      prompt: row.prompt,
    });

    const maxRetries = 3;
    const retryDelay = 2000; // 2 seconds

    const attemptGeneration = async (attempt: number): Promise<void> => {
      try {
        const client = new ApiClientFactory(sessionToken).getServicesClient();
        const template = generateTestsTemplate
          .replace('{generation_prompt}', row.prompt)
          .replace('{num_tests}', '10');

        const response = await client.getOpenAIJson(template);
        
        // Log the raw response
        console.log('Generated Tests JSON:', JSON.stringify(response, null, 2));
        
        // Check if response has valid test cases
        if (!response?.test_cases?.length) {
          throw new Error('No test cases in response');
        }
        
        // Type assertion to ensure correct behavior values
        const tests: Test[] = response.test_cases.map((test: any) => ({
          ...test,
          behavior: test.behavior as 'Reliability' | 'Compliance' | 'Robustness'
        }));
        
        setTestsDialog(prev => ({
          ...prev,
          tests,
          isLoading: false,
        }));
      } catch (error) {
        console.error(`Attempt ${attempt} failed:`, error);
        
        if (attempt < maxRetries) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, retryDelay));
          return attemptGeneration(attempt + 1);
        }
        
        // If all retries failed, set error state
        console.error('All retry attempts failed:', error);
        setTestsDialog(prev => ({
          ...prev,
          tests: [],
          isLoading: false,
        }));
      }
    };

    // Start the retry process
    await attemptGeneration(1);
  };

  const filteredData = useMemo(() => {
    return completePaths.filter(path => {
      const matchesSearch = searchTerm === '' || 
        path.prompt.toLowerCase().includes(searchTerm.toLowerCase()) ||
        path.requirement.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        path.scenario.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        path.persona.name.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesRequirement = filters.requirement === '' || 
        path.requirement.name === filters.requirement;
      const matchesScenario = filters.scenario === '' || 
        path.scenario.name === filters.scenario;
      const matchesPersona = filters.persona === '' || 
        path.persona.name === filters.persona;

      return matchesSearch && matchesRequirement && matchesScenario && matchesPersona;
    });
  }, [completePaths, searchTerm, filters]);

  const columns = [
    {
      id: 'requirement',
      label: 'Requirement',
      render: (row: any) => (
        <>
          <Typography variant="subtitle2">{row.requirement.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {row.requirement.description}
          </Typography>
        </>
      ),
    },
    {
      id: 'scenario',
      label: 'Scenario',
      render: (row: any) => (
        <>
          <Typography variant="subtitle2">{row.scenario.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {row.scenario.description}
          </Typography>
        </>
      ),
    },
    {
      id: 'persona',
      label: 'Persona',
      render: (row: any) => (
        <>
          <Typography variant="subtitle2">{row.persona.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {row.persona.description}
          </Typography>
        </>
      ),
    },
    {
      id: 'prompt',
      label: 'Generation Prompt',
      render: (row: any) => (
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {row.prompt}
          </Typography>
          <IconButton
            size="small"
            onClick={() => handleGenerateTests(row)}
            sx={{ mt: -0.5 }}
          >
            <ScienceIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            onClick={() => handleEdit(row, completePaths.indexOf(row))}
            sx={{ mt: -0.5 }}
          >
            <EditIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      {completePaths.length === 0 ? (
        <Box 
          sx={{ 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: 'center', 
            alignItems: 'center', 
            height: 300,
            gap: 2
          }}
        >
          <Typography variant="h6" color="text.secondary">
            No Combinations Generated
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 400, mb: 2 }}>
            Create connections between requirements, scenarios, and personas in the visualization view to generate combinations.
          </Typography>
          <Button
            variant="contained"
            color="primary"
            onClick={() => setTabValue(5)}
            startIcon={<VisibilityIcon />}
          >
            Go to Requirements Flow
          </Button>
        </Box>
      ) : (
        <>
          <Box sx={{ mb: 3, gap: 2, display: 'flex', flexDirection: 'column' }}>
            <TextField
              fullWidth
              label="Search prompts"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
            />
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                select
                label="Filter by Requirement"
                value={filters.requirement}
                onChange={(e) => setFilters({ ...filters, requirement: e.target.value })}
                size="small"
                sx={{ flex: 1 }}
              >
                <MenuItem value="">All Requirements</MenuItem>
                {requirements.map((req, index) => (
                  <MenuItem key={index} value={req.name}>{req.name}</MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label="Filter by Scenario"
                value={filters.scenario}
                onChange={(e) => setFilters({ ...filters, scenario: e.target.value })}
                size="small"
                sx={{ flex: 1 }}
              >
                <MenuItem value="">All Scenarios</MenuItem>
                {scenarios.map((scen, index) => (
                  <MenuItem key={index} value={scen.name}>{scen.name}</MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label="Filter by Persona"
                value={filters.persona}
                onChange={(e) => setFilters({ ...filters, persona: e.target.value })}
                size="small"
                sx={{ flex: 1 }}
              >
                <MenuItem value="">All Personas</MenuItem>
                {personas.map((pers, index) => (
                  <MenuItem key={index} value={pers.name}>{pers.name}</MenuItem>
                ))}
              </TextField>
            </Box>
          </Box>
          <BaseTable
            columns={columns}
            data={filteredData}
          />
          <EditPromptDialog
            open={editDialog.open}
            onClose={() => setEditDialog({ ...editDialog, open: false })}
            onSave={handleSavePrompt}
            prompt={editDialog.prompt}
            requirement={editDialog.requirement}
            scenario={editDialog.scenario}
            persona={editDialog.persona}
          />
          <TestsDialog
            open={testsDialog.open}
            onClose={() => setTestsDialog(prev => ({ ...prev, open: false }))}
            tests={testsDialog.tests}
            setTests={(tests) => setTestsDialog(prev => ({ ...prev, tests }))}
            isLoading={testsDialog.isLoading}
            setIsLoading={(isLoading) => setTestsDialog(prev => ({ ...prev, isLoading }))}
            prompt={testsDialog.prompt}
            sessionToken={sessionToken}
          />
        </>
      )}
    </Box>
  );
} 