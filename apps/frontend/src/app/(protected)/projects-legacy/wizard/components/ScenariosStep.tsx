import * as React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import EditableTable from './EditableTable';

interface ScenariosStepProps {
  data?: Array<{
    name: string;
    description: string;
  }>;
  onNext: () => void;
  onBack: () => void;
}

export default function ScenariosStep({ data, onNext, onBack }: ScenariosStepProps) {
  const [scenarios, setScenarios] = React.useState(
    data?.map((scenario, index) => ({
      id: `scenario-${index}`,
      name: scenario.name,
      description: scenario.description,
    })) || []
  );

  const columns = [
    { id: 'name', label: 'Scenario' },
    { id: 'description', label: 'Description' },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNext();
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Test Scenarios
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Define the test scenarios that will be used to validate your system&apos;s behavior.
        </Typography>
        <EditableTable
          data={scenarios}
          columns={columns}
          onUpdate={setScenarios}
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