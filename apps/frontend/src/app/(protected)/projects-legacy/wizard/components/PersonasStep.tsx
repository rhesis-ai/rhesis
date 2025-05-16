import * as React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import EditableTable from './EditableTable';

interface PersonasStepProps {
  data?: Array<{
    name: string;
    description: string;
  }>;
  onNext: () => void;
  onBack: () => void;
}

export default function PersonasStep({ data, onNext, onBack }: PersonasStepProps) {
  const [personas, setPersonas] = React.useState(
    data?.map((persona, index) => ({
      id: `persona-${index}`,
      name: persona.name,
      description: persona.description,
    })) || []
  );

  const columns = [
    { id: 'name', label: 'Persona' },
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
          User Personas
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Define the different types of users who will interact with your system.
        </Typography>
        <EditableTable
          data={personas}
          columns={columns}
          onUpdate={setPersonas}
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