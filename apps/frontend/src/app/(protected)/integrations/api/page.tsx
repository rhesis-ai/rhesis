'use client';

import { Box, Paper, Typography, Button, Stack, Chip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';

export default function APIsPage() {
  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h4" sx={{ mb: 1 }}>
            APIs
          </Typography>
          <Typography color="text.secondary">
            Connect to REST API endpoints to enhance your evaluation and testing
            workflows.
          </Typography>
        </Box>

        <Stack spacing={3}>
          {/* Add API Card */}
          <Paper
            sx={{
              p: 3,
              display: 'flex',
              flexDirection: 'column',
              bgcolor: 'action.hover',
              position: 'relative',
            }}
          >
            <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
              <Chip label="Coming soon" size="small" variant="outlined" />
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <AddIcon
                sx={{
                  fontSize: theme => theme.iconSizes.large,
                  color: 'grey.500',
                }}
              />
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" color="text.secondary">
                  Add API
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Connect to your REST API endpoints
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
                  borderRadius: theme => theme.shape.borderRadius * 1.5,
                }}
              >
                Add API
              </Button>
            </Box>
          </Paper>
        </Stack>
      </Box>
    </Box>
  );
}
