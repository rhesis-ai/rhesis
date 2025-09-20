'use client';

import { Box, Paper, Typography, Button, Stack, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';

export default function ToolsPage() {
  const handleAddTool = () => {
    // Disabled for now - coming soon
    console.log('Add tool - coming soon');
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>Development Tools</Typography>
        <Typography color="text.secondary">
          Connect your monitoring, logging, and analytics tools to enhance your development workflow.
        </Typography>
      </Box>

      <Stack spacing={3}>
        {/* Add Tool Card */}
        <Paper 
          sx={{ 
            p: 3, 
            display: 'flex', 
            flexDirection: 'column',
            bgcolor: 'action.hover',
            position: 'relative'
          }}
        >
          <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
            <Chip 
              label="Coming soon" 
              size="small" 
              variant="outlined"
            />
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <AddIcon sx={{ fontSize: 32, color: 'grey.500' }} />
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6" color="text.secondary">Add Tool</Typography>
              <Typography color="text.secondary" variant="body2">
                Connect to monitoring, logging, and analytics tools
              </Typography>
            </Box>
          </Box>
          
          <Box sx={{ mt: 'auto' }}>
            <Button
              fullWidth
              variant="outlined"
              size="small"
              disabled
              sx={{ 
                textTransform: 'none',
                borderRadius: 1.5
              }}
            >
              Add Tool
            </Button>
          </Box>
        </Paper>
      </Stack>
    </Box>
  );
} 