import * as React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import EditableTable from './EditableTable';

interface RequirementsStepProps {
  data?: Array<{
    name: string;
    description: string;
  }>;
  onNext: () => void;
  onBack: () => void;
}

export default function RequirementsStep({ data, onNext, onBack }: RequirementsStepProps) {
  const [requirements, setRequirements] = React.useState(
    data?.map((req, index) => ({
      id: `req-${index}`,
      name: req.name,
      description: req.description,
    })) || []
  );

  const columns = [
    { id: 'name', label: 'Requirement' },
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
          System Requirements
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Define the functional and non-functional requirements of your system.
        </Typography>
        <EditableTable
          data={requirements}
          columns={columns}
          onUpdate={setRequirements}
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