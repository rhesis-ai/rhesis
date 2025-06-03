import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
} from '@mui/material';

interface NodeEditDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: { name: string; description: string }) => void;
  data: {
    name: string;
    description: string;
  };
  title: string;
}

export default function NodeEditDialog({
  open,
  onClose,
  onSave,
  data,
  title,
}: NodeEditDialogProps) {
  const [name, setName] = React.useState(data.name);
  const [description, setDescription] = React.useState(data.description);

  React.useEffect(() => {
    setName(data.name);
    setDescription(data.description);
  }, [data]);

  const handleSave = () => {
    onSave({ name, description });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Edit {title}</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          label="Name"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          margin="dense"
          label="Description"
          fullWidth
          multiline
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
} 