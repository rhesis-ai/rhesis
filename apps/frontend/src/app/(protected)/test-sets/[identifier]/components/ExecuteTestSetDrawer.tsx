import { useState, useEffect } from 'react';
import {
  Drawer,
  Box,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  ToggleButton,
  CircularProgress,
  Alert,
  Chip,
  AppBar,
  Toolbar,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

interface ExecuteTestSetDrawerProps {
  open: boolean;
  onClose: () => void;
  testSetId: string;
  sessionToken: string;
}

export default function ExecuteTestSetDrawer({ 
  open, 
  onClose, 
  testSetId,
  sessionToken 
}: ExecuteTestSetDrawerProps) {
  const [selectedEndpoints, setSelectedEndpoints] = useState<string[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch endpoints when drawer opens
  useEffect(() => {
    if (open) {
      const fetchEndpoints = async () => {
        setLoading(true);
        try {
          const apiFactory = new ApiClientFactory(sessionToken);
          const endpointsClient = apiFactory.getEndpointsClient();
          const response = await endpointsClient.getEndpoints();
          setEndpoints(response.data);
        } catch (err) {
          setError('Failed to load endpoints');
        } finally {
          setLoading(false);
        }
      };
      fetchEndpoints();
    }
  }, [open, sessionToken]);

  const handleEndpointToggle = (endpointId: string) => {
    setSelectedEndpoints(prev => 
      prev.includes(endpointId) 
        ? prev.filter(id => id !== endpointId)
        : [...prev, endpointId]
    );
  };

  const handleExecute = async () => {
    if (selectedEndpoints.length === 0) return;

    setExecuting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();
      
      // Execute test set against each selected endpoint
      const results = await Promise.all(
        selectedEndpoints.map(endpointId => 
          testSetsClient.executeTestSet(testSetId, endpointId)
        )
      );
      
      // Show success message
      setSuccessMessage(`Successfully started ${results.length} test execution${results.length > 1 ? 's' : ''}`);
      
      // Close drawer after a short delay
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (err) {
      setError('Failed to execute test set');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: 400 }
      }}
    >
      <AppBar 
        position="relative" 
        color="default" 
        elevation={0} 
        sx={{ 
          borderBottom: 1, 
          borderColor: 'divider',
          bgcolor: 'background.paper'
        }}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ color: 'text.primary' }}>
            Execute Test Set
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Box sx={{ 
        p: 3,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        height: '100%',
        overflow: 'auto'
      }}>
        {error && (
          <Alert severity="error">
            {error}
          </Alert>
        )}

        {successMessage && (
          <Alert severity="success">
            {successMessage}
          </Alert>
        )}

        <Typography variant="body1" color="text.secondary">
          Select endpoints to execute this test set against. You can select multiple endpoints to run the tests in parallel.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <List>
            {endpoints.map((endpoint) => (
              <ListItem 
                key={endpoint.id}
                disablePadding
                sx={{ mb: 1 }}
              >
                <ToggleButton
                  value={endpoint.id}
                  selected={selectedEndpoints.includes(endpoint.id)}
                  onChange={() => handleEndpointToggle(endpoint.id)}
                  sx={{ 
                    width: '100%', 
                    justifyContent: 'flex-start',
                    textAlign: 'left',
                    p: 2,
                    gap: 1,
                    flexDirection: 'column',
                    alignItems: 'flex-start'
                  }}
                >
                  <Box sx={{ 
                    width: '100%',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <Typography variant="subtitle1" sx={{ textTransform: 'none' }}>
                      {endpoint.name}
                    </Typography>
                    <Chip 
                      label={endpoint.environment.charAt(0).toUpperCase() + endpoint.environment.slice(1)}
                      size="small"
                      color={
                        endpoint.environment === 'production' ? 'success' :
                        endpoint.environment === 'staging' ? 'warning' : 'info'
                      }
                      variant="outlined"
                    />
                  </Box>
                  {endpoint.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, textTransform: 'none' }}>
                      {endpoint.description}
                    </Typography>
                  )}
                </ToggleButton>
              </ListItem>
            ))}
          </List>
        )}

        <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            onClick={handleExecute}
            disabled={selectedEndpoints.length === 0 || executing}
          >
            {executing ? 'Executing...' : `Execute (${selectedEndpoints.length} selected)`}
          </Button>
          <Button
            variant="outlined"
            onClick={onClose}
            disabled={executing}
          >
            Cancel
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
} 