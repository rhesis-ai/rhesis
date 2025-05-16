import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Collapse,
  IconButton,
  Divider,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface PathDetailsPanelProps {
  open: boolean;
  onClose: () => void;
  requirement?: {
    name: string;
    description: string;
  } | null;
  scenario?: {
    name: string;
    description: string;
  } | null;
  persona?: {
    name: string;
    description: string;
  } | null;
}

export default function PathDetailsPanel({
  open,
  onClose,
  requirement = null,
  scenario = null,
  persona = null,
}: PathDetailsPanelProps) {
  const [expanded, setExpanded] = React.useState(true);

  // Don't render if no data is available
  if (!requirement || !scenario || !persona) {
    return null;
  }

  return (
    <Collapse in={open} sx={{ position: 'absolute', bottom: 16, right: 16, width: 400, zIndex: 1000 }}>
      <Paper elevation={3} sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h6">Complete Path Details</Typography>
          <Box>
            <IconButton size="small" onClick={() => setExpanded(!expanded)}>
              {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
            <IconButton size="small" onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
        <Collapse in={expanded}>
          <Box sx={{ mt: 1 }}>
            <Typography variant="subtitle1" color="primary" gutterBottom>
              Requirement
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {requirement.name || 'No name available'}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {requirement.description || 'No description available'}
            </Typography>
            
            <Divider sx={{ my: 2 }} />
            
            <Typography variant="subtitle1" color="primary" gutterBottom>
              Scenario
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {scenario.name || 'No name available'}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {scenario.description || 'No description available'}
            </Typography>
            
            <Divider sx={{ my: 2 }} />
            
            <Typography variant="subtitle1" color="primary" gutterBottom>
              Persona
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              {persona.name || 'No name available'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {persona.description || 'No description available'}
            </Typography>
          </Box>
        </Collapse>
      </Paper>
    </Collapse>
  );
} 