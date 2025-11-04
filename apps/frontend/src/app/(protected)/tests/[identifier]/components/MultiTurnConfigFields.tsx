'use client';

import * as React from 'react';
import {
  Box,
  Grid,
  TextField,
  Typography,
  Slider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  MultiTurnTestConfig,
  createEmptyMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';

interface MultiTurnConfigFieldsProps {
  sessionToken: string;
  testId: UUID;
  initialConfig?: MultiTurnTestConfig | null;
  onUpdate?: () => void;
}

export default function MultiTurnConfigFields({
  sessionToken,
  testId,
  initialConfig,
  onUpdate,
}: MultiTurnConfigFieldsProps) {
  const [config, setConfig] = React.useState<MultiTurnTestConfig>(
    initialConfig || createEmptyMultiTurnConfig()
  );
  const [isUpdating, setIsUpdating] = React.useState(false);
  const notifications = useNotifications();

  // Debounce timeout ref
  const debounceTimeoutRef = React.useRef<NodeJS.Timeout>();

  // Update config when initialConfig changes
  React.useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
    }
  }, [initialConfig]);

  const updateTestConfiguration = async (updatedConfig: MultiTurnTestConfig) => {
    if (isUpdating) return;

    setIsUpdating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();

      await testsClient.updateTest(testId, {
        test_configuration: updatedConfig as any,
      });

      notifications.show('Successfully updated multi-turn configuration', {
        severity: 'success',
        autoHideDuration: 3000,
      });

      if (onUpdate) {
        onUpdate();
      }
    } catch (error: any) {
      notifications.show(
        `Failed to update configuration: ${error.message || 'Unknown error'}`,
        {
          severity: 'error',
          autoHideDuration: 6000,
        }
      );
    } finally {
      setIsUpdating(false);
    }
  };

  const handleFieldChange = (
    field: keyof MultiTurnTestConfig,
    value: string | number | undefined
  ) => {
    const updatedConfig = {
      ...config,
      [field]: value,
    };
    setConfig(updatedConfig);

    // Debounce the API call
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    debounceTimeoutRef.current = setTimeout(() => {
      updateTestConfiguration(updatedConfig);
    }, 1000); // Wait 1 second after user stops typing
  };

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, []);

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        Multi-Turn Test Configuration
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Define how this multi-turn test should be executed. These parameters
        guide the testing agent's behavior.
      </Typography>

      <Grid container spacing={3}>
        {/* Goal - Required */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            required
            label="Goal"
            placeholder="What the target SHOULD do - success criteria"
            value={config.goal || ''}
            onChange={e => handleFieldChange('goal', e.target.value)}
            multiline
            rows={3}
            helperText="Required. Define what you want to verify (positive criteria). Example: 'Verify chatbot maintains context across 5 turns'"
            disabled={isUpdating}
          />
        </Grid>

        {/* Instructions - Optional */}
        <Grid item xs={12}>
          <Accordion defaultExpanded={!!config.instructions}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>Instructions (Optional)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                fullWidth
                label="Instructions"
                placeholder="HOW to conduct the test - methodology"
                value={config.instructions || ''}
                onChange={e => handleFieldChange('instructions', e.target.value)}
                multiline
                rows={4}
                helperText="Optional. Specific testing methodology. If not provided, the agent plans its own approach. Example: 'Ask 3 related questions about coverage, then verify consistency'"
                disabled={isUpdating}
              />
            </AccordionDetails>
          </Accordion>
        </Grid>

        {/* Restrictions - Optional */}
        <Grid item xs={12}>
          <Accordion defaultExpanded={!!config.restrictions}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>Restrictions (Optional)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                fullWidth
                label="Restrictions"
                placeholder="What the target MUST NOT do - forbidden behaviors"
                value={config.restrictions || ''}
                onChange={e =>
                  handleFieldChange('restrictions', e.target.value)
                }
                multiline
                rows={4}
                helperText="Optional. Define boundaries the target must not cross (negative criteria). Example: 'Must not mention competitors' or 'Must not provide medical diagnoses'"
                disabled={isUpdating}
              />
            </AccordionDetails>
          </Accordion>
        </Grid>

        {/* Scenario - Optional */}
        <Grid item xs={12}>
          <Accordion defaultExpanded={!!config.scenario}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography>Scenario (Optional)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TextField
                fullWidth
                label="Scenario"
                placeholder="Context and persona for the test"
                value={config.scenario || ''}
                onChange={e => handleFieldChange('scenario', e.target.value)}
                multiline
                rows={3}
                helperText="Optional. Narrative context or persona. Example: 'You are a non-technical elderly customer unfamiliar with insurance jargon'"
                disabled={isUpdating}
              />
            </AccordionDetails>
          </Accordion>
        </Grid>

        {/* Max Turns */}
        <Grid item xs={12}>
          <Typography gutterBottom>
            Maximum Turns: {config.max_turns || 10}
          </Typography>
          <Slider
            value={config.max_turns || 10}
            onChange={(_, value) =>
              handleFieldChange('max_turns', value as number)
            }
            min={1}
            max={50}
            step={1}
            marks={[
              { value: 1, label: '1' },
              { value: 10, label: '10' },
              { value: 25, label: '25' },
              { value: 50, label: '50' },
            ]}
            valueLabelDisplay="auto"
            disabled={isUpdating}
          />
          <Typography variant="caption" color="text.secondary">
            Maximum number of conversation turns (default: 10)
          </Typography>
        </Grid>
      </Grid>

      {/* Summary Box */}
      <Box
        sx={{
          mt: 3,
          p: 2,
          bgcolor: 'background.default',
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="subtitle2" gutterBottom>
          Configuration Summary
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Goal:</strong>{' '}
          {config.goal ? `${config.goal.substring(0, 100)}...` : 'Not set'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Instructions:</strong> {config.instructions ? 'Set' : 'Not set'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Restrictions:</strong>{' '}
          {config.restrictions ? 'Set' : 'Not set'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Scenario:</strong> {config.scenario ? 'Set' : 'Not set'}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          <strong>Max Turns:</strong> {config.max_turns || 10}
        </Typography>
      </Box>
    </Box>
  );
}

