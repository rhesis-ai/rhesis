import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
} from '@mui/material';

interface EditPromptDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (newPrompt: string) => void;
  prompt: string;
  requirement: { name: string; description: string };
  scenario: { name: string; description: string };
  persona: { name: string; description: string };
}

export default function EditPromptDialog({
  open,
  onClose,
  onSave,
  prompt,
  requirement,
  scenario,
  persona,
}: EditPromptDialogProps) {
  const [editedPrompt, setEditedPrompt] = React.useState(prompt);

  React.useEffect(() => {
    setEditedPrompt(prompt);
  }, [prompt]);

  const handleSave = () => {
    onSave(editedPrompt);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Edit Prompt</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3, mt: 2 }}>
          <Typography variant="subtitle2" color="primary" gutterBottom>
            Requirement
          </Typography>
          <Typography variant="body2" gutterBottom>
            <strong>{requirement.name}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {requirement.description}
          </Typography>

          <Typography variant="subtitle2" color="primary" gutterBottom>
            Scenario
          </Typography>
          <Typography variant="body2" gutterBottom>
            <strong>{scenario.name}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {scenario.description}
          </Typography>

          <Typography variant="subtitle2" color="primary" gutterBottom>
            Persona
          </Typography>
          <Typography variant="body2" gutterBottom>
            <strong>{persona.name}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {persona.description}
          </Typography>
        </Box>

        <TextField
          fullWidth
          multiline
          rows={6}
          value={editedPrompt}
          onChange={(e) => setEditedPrompt(e.target.value)}
          label="Prompt"
          variant="outlined"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
} 