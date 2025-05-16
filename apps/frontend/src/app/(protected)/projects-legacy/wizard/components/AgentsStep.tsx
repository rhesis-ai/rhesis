import * as React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import EditableTable from './EditableTable';

interface AgentsStepProps {
  data?: Array<{
    name: string;
    description: string;
    responsibilities: string[];
  }>;
  onNext: () => void;
  onBack: () => void;
}

export default function AgentsStep({ data, onNext, onBack }: AgentsStepProps) {
  const [agents, setAgents] = React.useState(
    data?.map((agent, index) => ({
      id: `agent-${index}`,
      name: agent.name,
      description: agent.description,
      responsibilities: agent.responsibilities.join('\n'),
    })) || []
  );

  const columns = [
    { id: 'name', label: 'Name' },
    { id: 'description', label: 'Description' },
    { id: 'responsibilities', label: 'Responsibilities' },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNext();
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          System Agents
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Define the agents that will be part of your system. For responsibilities, use new lines to separate multiple items.
        </Typography>
        <EditableTable
          data={agents}
          columns={columns}
          onUpdate={setAgents}
        />
      </Paper>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
        <Button onClick={onBack}>Back</Button>
        <Button type="submit" variant="contained">
          Next
        </Button>
      </Box>
    </Box>
  );
} 