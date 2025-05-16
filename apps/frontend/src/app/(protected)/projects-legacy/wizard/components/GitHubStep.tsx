import * as React from 'react';
import { Box, Paper, TextField, Button, Typography, CircularProgress, Tabs, Tab } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { auth } from '@/auth';
import EditableTable from './EditableTable';
import systemTemplate from '../../templates/extract_system.md';
import agentsTemplate from '../../templates/extract_agents.md';
import requirementsTemplate from '../../templates/extract_requirements.md';
import scenariosTemplate from '../../templates/extract_scenarios.md';
import personasTemplate from '../../templates/extract_personas.md';
import GitHubIcon from '@mui/icons-material/GitHub';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PsychologyIcon from '@mui/icons-material/Psychology';
import InfoIcon from '@mui/icons-material/Info';
import CheckIcon from '@mui/icons-material/Check';

interface GitHubStepProps {
  onNext: (data: any) => void;
  sessionToken: string;
}

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
        <Box sx={{ pt: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

// Add this type near the top with other interfaces
type AnalysisStatus = {
  system: boolean;
  agents: boolean;
  requirements: boolean;
  scenarios: boolean;
  personas: boolean;
};

export default function GitHubStep({ onNext, sessionToken }: GitHubStepProps) {
  const [url, setUrl] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [metadata, setMetadata] = React.useState<any>(null);
  const [systemData, setSystemData] = React.useState({ name: '', description: '' });
  const [goals, setGoals] = React.useState<Array<{ id: string; description: string }>>([]);
  const [capabilities, setCapabilities] = React.useState<Array<{ id: string; description: string }>>([]);
  const [agents, setAgents] = React.useState<Array<{ id: string; name: string; description: string; responsibilities: string }>>([]);
  const [tabValue, setTabValue] = React.useState(0);
  const [operation, setOperation] = React.useState<'idle' | 'reading' | 'analyzing_system' | 'analyzing_agents' | 'analyzing_requirements' | 'analyzing_scenarios' | 'analyzing_personas' | 'success'>('idle');
  const [analysisStatus, setAnalysisStatus] = React.useState<AnalysisStatus>({
    system: false,
    agents: false,
    requirements: false,
    scenarios: false,
    personas: false
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setAnalysisStatus({
      system: false,
      agents: false,
      requirements: false,
      scenarios: false,
      personas: false
    });

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();
      
      let contents;
      try {
        setOperation('reading');
        contents = await servicesClient.getGitHubContents(url);
      } catch (error) {
        console.error('GitHub API error:', error);
        throw new Error('Unable to access repository. Please check the URL and ensure it is public or you have access to it.');
      }

      const maxRetries = 3;
      const retryDelay = 2000; // 2 seconds

      const retryAnalysis = async (template: string, type: keyof AnalysisStatus): Promise<any> => {
        let lastError;
        
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
          try {
            const data = await servicesClient.getOpenAIJson(template.replace('{codebase}', contents));
            setAnalysisStatus(prev => ({ ...prev, [type]: true }));
            return data;
          } catch (error) {
            console.error(`${type} analysis attempt ${attempt} failed:`, error);
            lastError = error;
            if (attempt < maxRetries) {
              await new Promise(resolve => setTimeout(resolve, retryDelay));
            }
          }
        }
        throw lastError;
      };

      try {
        // Run all analysis in parallel with retry mechanism
        const [systemData, agentsData, requirementsData, scenariosData, personasData] = await Promise.all([
          retryAnalysis(systemTemplate, 'system'),
          retryAnalysis(agentsTemplate, 'agents'),
          retryAnalysis(requirementsTemplate, 'requirements'),
          retryAnalysis(scenariosTemplate, 'scenarios'),
          retryAnalysis(personasTemplate, 'personas')
        ]);

        // Combine all metadata
        const metadata = {
          system: systemData.system,
          agents: agentsData.agents,
          requirements: requirementsData.requirements,
          scenarios: scenariosData.scenarios,
          personas: personasData.personas
        };

        if (!metadata?.system) {
          throw new Error('Unable to extract system information from repository.');
        }

        setMetadata(metadata);
        setSystemData({
          name: metadata.system.name || '',
          description: metadata.system.description || ''
        });
        setGoals(metadata.system.primary_goals?.map((goal: string, index: number) => ({
          id: `goal-${index}`,
          description: goal
        })) || []);
        setCapabilities(metadata.system.key_capabilities?.map((capability: string, index: number) => ({
          id: `capability-${index}`,
          description: capability
        })) || []);
        setAgents(metadata.agents?.map((agent: any, index: number) => ({
          id: `agent-${index}`,
          name: agent.name,
          description: agent.description,
          responsibilities: agent.responsibilities.join('\n')
        })) || []);

        setOperation('success');
        setTimeout(() => {
          setOperation('idle');
        }, 3000);
      } catch (error) {
        setError((error as Error).message || 'An unexpected error occurred. Please try again.');
        setOperation('idle');
      }
    } catch (error) {
      setError((error as Error).message || 'An unexpected error occurred. Please try again.');
      setOperation('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    const updatedMetadata = {
      ...metadata,
      system: {
        ...metadata.system,
        name: systemData.name,
        description: systemData.description,
        primary_goals: goals.map(g => g.description),
        key_capabilities: capabilities.map(c => c.description)
      },
      agents: agents.map(agent => ({
        name: agent.name,
        description: agent.description,
        responsibilities: agent.responsibilities.split('\n')
      }))
    };
    onNext(updatedMetadata);
  };

  const getButtonContent = () => {
    switch (operation) {
      case 'reading':
        return {
          text: 'Reading Repository...',
          icon: <FolderOpenIcon />
        };
      case 'analyzing_system':
        return {
          text: 'Analyzing System...',
          icon: <PsychologyIcon />
        };
      case 'analyzing_agents':
        return {
          text: 'Analyzing Agents...',
          icon: <PsychologyIcon />
        };
      case 'analyzing_requirements':
        return {
          text: 'Analyzing Requirements...',
          icon: <PsychologyIcon />
        };
      case 'analyzing_scenarios':
        return {
          text: 'Analyzing Scenarios...',
          icon: <PsychologyIcon />
        };
      case 'analyzing_personas':
        return {
          text: 'Analyzing Personas...',
          icon: <PsychologyIcon />
        };
      case 'success':
        return {
          text: 'Analysis Complete!',
          icon: <InfoIcon />
        };
      default:
        return {
          text: 'Connect and Analyze',
          icon: <GitHubIcon />
        };
    }
  };

  const buttonContent = getButtonContent();

  // Add this component to show analysis progress
  const AnalysisProgress = () => (
    <Box sx={{ mt: 2 }}>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Analysis Progress:
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        {Object.entries(analysisStatus).map(([key, completed]) => (
          <Box key={key} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {completed ? (
              <CheckIcon color="success" sx={{ fontSize: 20 }} />
            ) : (
              <CircularProgress size={20} />
            )}
            <Typography variant="body2">
              {key.charAt(0).toUpperCase() + key.slice(1)}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <GitHubIcon sx={{ fontSize: 28 }} />
          <Typography variant="h6">
            Connect to GitHub
          </Typography>
        </Box>
        
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1, 
          mb: 3, 
          p: 2, 
          bgcolor: 'info.lighter',
          borderRadius: 1 
        }}>
          <InfoIcon color="info" />
          <Box>
            <Typography variant="body2" color="info.dark">
              You can connect any repository that implements agents, including popular frameworks like LangChain, LangGraph, CrewAI, and AutoGen.
            </Typography>
          </Box>
        </Box>

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="GitHub Repository URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            margin="normal"
            error={!!error}
            helperText={error}
            disabled={loading}
          />
          <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              type="submit"
              variant="contained"
              disabled={!url || loading}
              startIcon={loading ? undefined : <GitHubIcon />}
            >
              {loading ? 'Analyzing...' : 'Connect and Analyze'}
            </Button>
          </Box>
          {loading && <AnalysisProgress />}
        </form>

        {operation === 'success' && (
          <Typography 
            color="success.main" 
            sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <InfoIcon /> Repository analysis completed successfully!
          </Typography>
        )}
      </Paper>

      {metadata && (
        <Box component="form" onSubmit={handleNext}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Tabs value={tabValue} onChange={handleTabChange}>
              <Tab label="Basic Information" />
              <Tab label="Goals & Capabilities" />
              <Tab label="Agents" />
            </Tabs>

            <TabPanel value={tabValue} index={0}>
              <Typography variant="h6" gutterBottom>
                Basic Information
              </Typography>
              <TextField
                fullWidth
                label="System Name"
                value={systemData.name}
                onChange={(e) => setSystemData({ ...systemData, name: e.target.value })}
                margin="normal"
                required
              />
              <TextField
                fullWidth
                label="Description"
                value={systemData.description}
                onChange={(e) => setSystemData({ ...systemData, description: e.target.value })}
                margin="normal"
                multiline
                rows={4}
                required
              />
            </TabPanel>

            <TabPanel value={tabValue} index={1}>
              <Typography variant="h6" gutterBottom>
                Primary Goals
              </Typography>
              <EditableTable
                data={goals}
                columns={[{ id: 'description', label: 'Goal' }]}
                onUpdate={setGoals}
              />
              
              <Box sx={{ mt: 4 }}>
                <Typography variant="h6" gutterBottom>
                  Key Capabilities
                </Typography>
                <EditableTable
                  data={capabilities}
                  columns={[{ id: 'description', label: 'Capability' }]}
                  onUpdate={setCapabilities}
                />
              </Box>
            </TabPanel>

            <TabPanel value={tabValue} index={2}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Define the agents that will be part of your system. For responsibilities, use new lines to separate multiple items.
              </Typography>
              <EditableTable
                data={agents}
                columns={[
                  { id: 'name', label: 'Name' },
                  { id: 'description', label: 'Description' },
                  { id: 'responsibilities', label: 'Responsibilities' }
                ]}
                onUpdate={setAgents}
              />
            </TabPanel>
          </Paper>

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
            <Button type="submit" variant="contained">
              Next
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
} 